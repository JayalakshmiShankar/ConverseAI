import os
import torch
import torchaudio
from torchaudio.pipelines import (
    WAV2VEC2_ASR_LARGE_960H,
    VOXPOPULI_ASR_BASE_10K_ES,
    VOXPOPULI_ASR_BASE_10K_DE
)
from typing import List, Dict, Any
import numpy as np

class PhonemeScorer:
    def __init__(self):
        # Cache for models to avoid re-loading
        self._models = {}
        self._labels = {}
        self._bundles = {
            "en-US": WAV2VEC2_ASR_LARGE_960H,
            "en-GB": WAV2VEC2_ASR_LARGE_960H,
            "es-ES": VOXPOPULI_ASR_BASE_10K_ES,
            "de-DE": VOXPOPULI_ASR_BASE_10K_DE,
        }
        
    def _get_bundle(self, language_id: str):
        return self._bundles.get(language_id, WAV2VEC2_ASR_LARGE_960H)

    def _get_model(self, language_id: str):
        if language_id not in self._models:
            bundle = self._get_bundle(language_id)
            self._models[language_id] = bundle.get_model()
            self._labels[language_id] = bundle.get_labels()
        return self._models[language_id], self._labels[language_id], self._get_bundle(language_id)
        
    def _preprocess_audio(self, audio_path: str, bundle) -> torch.Tensor:
        waveform, sample_rate = torchaudio.load(audio_path)
        if sample_rate != bundle.sample_rate:
            waveform = torchaudio.transforms.Resample(sample_rate, bundle.sample_rate)(waveform)
        
        # Convert to mono if stereo
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
            
        return waveform

    def get_phoneme_scores(self, audio_path: str, target_sentence: str, language_id: str = "en-US") -> Dict[str, Any]:
        model, labels, bundle = self._get_model(language_id)
        waveform = self._preprocess_audio(audio_path, bundle)
        
        with torch.inference_mode():
            emission, _ = model(waveform)
            
        # Get the most likely tokens for each frame
        probs = torch.nn.functional.softmax(emission, dim=-1)
        max_probs, max_indices = torch.max(probs, dim=-1)
        
        frames = []
        for i in range(max_indices.shape[1]):
            idx = max_indices[0, i].item()
            conf = max_probs[0, i].item()
            if idx < len(labels):
                label = labels[idx]
                if label != '-': # Ignore blank tokens
                    frames.append({"label": label, "confidence": conf})
        
        detected_phonemes = []
        if frames:
            current_ph = frames[0]["label"]
            current_conf = [frames[0]["confidence"]]
            for f in frames[1:]:
                if f["label"] == current_ph:
                    current_conf.append(f["confidence"])
                else:
                    detected_phonemes.append({
                        "phoneme": current_ph,
                        "confidence": float(np.mean(current_conf))
                    })
                    current_ph = f["label"]
                    current_conf = [f["confidence"]]
            detected_phonemes.append({
                "phoneme": current_ph,
                "confidence": float(np.mean(current_conf))
            })

        target_words = target_sentence.upper().split()
        word_feedback = []
        total_phoneme_score = 0
        phoneme_count = 0
        
        ph_idx = 0
        for word in target_words:
            word_phonemes = []
            word_score_sum = 0
            word_ph_count = 0
            
            for char in word:
                found = False
                for search_idx in range(ph_idx, min(ph_idx + 5, len(detected_phonemes))):
                    if detected_phonemes[search_idx]["phoneme"] == char:
                        conf = detected_phonemes[search_idx]["confidence"]
                        word_phonemes.append({"char": char, "score": conf, "status": "correct" if conf > 0.7 else "close"})
                        word_score_sum += conf
                        ph_idx = search_idx + 1
                        found = True
                        break
                
                if not found:
                    word_phonemes.append({"char": char, "score": 0.0, "status": "wrong"})
                
                word_ph_count += 1
                phoneme_count += 1
                total_phoneme_score += word_phonemes[-1]["score"]
            
            word_feedback.append({
                "word": word,
                "phonemes": word_phonemes,
                "score": (word_score_sum / word_ph_count) if word_ph_count > 0 else 0
            })

        final_score = (total_phoneme_score / phoneme_count) * 10 if phoneme_count > 0 else 0
        
        return {
            "final_score": round(final_score, 2),
            "word_feedback": word_feedback
        }

# Global instance for API use
scorer = PhonemeScorer()
