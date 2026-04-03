(() => {
  const correctCountEl = document.getElementById("correctCount");
  const wrongCountEl = document.getElementById("wrongCount");
  const streakCountEl = document.getElementById("streakCount");
  const progressText = document.getElementById("progressText");
  const scorePill = document.getElementById("scorePill");
  const progressFill = document.getElementById("progressFill");
  const categoryTabs = document.getElementById("categoryTabs");
  const targetWord = document.getElementById("targetWord");
  const ipaText = document.getElementById("ipaText");
  const meaningText = document.getElementById("meaningText");
  const hintContent = document.getElementById("hintContent");
  const micZone = document.getElementById("micZone");
  const micStatus = document.getElementById("micStatus");
  const micAnimations = document.getElementById("micAnimations");
  const listenBtn = document.getElementById("listenBtn");
  const recBtn = document.getElementById("recBtn");
  const skipBtn = document.getElementById("skipBtn");
  const resultPanel = document.getElementById("resultPanel");
  const resultIcon = document.getElementById("resultIcon");
  const resultTitle = document.getElementById("resultTitle");
  const transcriptText = document.getElementById("transcriptText");
  const syllableChips = document.getElementById("syllableChips");
  const correctionBox = document.getElementById("correctionBox");
  const correctionGuide = document.getElementById("correctionGuide");
  const aiFeedback = document.getElementById("aiFeedback");
  const aiLoading = document.getElementById("aiLoading");
  const nextBtn = document.getElementById("nextBtn");
  const prevBtn = document.getElementById("prevBtn");
  const quizCard = document.getElementById("quizCard");
  const completionScreen = document.getElementById("completionScreen");
  const gradeVal = document.getElementById("gradeVal");
  const restartBtn = document.getElementById("restartBtn");
  const topicChip = document.getElementById("topicChip");
  const questionNum = document.getElementById("questionNum");

  const GERMAN_WORDS = [
    // Category: Umlaute
    { 
      word: "über", 
      phonetic: "/ˈyːbɐ/", 
      meaning: "over/above", 
      cat: "Umlaute", 
      syllables: ["ü", "ber"], 
      hint: `The <span class="ph">ü</span> is like English "ee" but with rounded lips — say "ee" then pucker lips. Never "oo" or "u".`,
      correction: `Round lips for "oo" while tongue stays in "ee" position. <span class="ph">ü-ber</span>, stress first syllable.`,
      acceptableVariants: ["uber", "über", "ueber", "eber"]
    },
    { 
      word: "schön", 
      phonetic: "/ʃøːn/", 
      meaning: "beautiful/nice", 
      cat: "Umlaute", 
      syllables: ["schön"], 
      hint: "<span class=\"ph\">ö</span> = say \"e\" (as in bed) then round lips. <span class=\"ph\">sch</span> = \"sh\". Don't confuse with schon (already).",
      correction: `"sh" + rounded-e + "n". "shern" approx. Keep <span class="ph">ö</span> pure, no glide.`,
      acceptableVariants: ["schön", "schon", "shen", "shern", "shon"]
    },
    { 
      word: "Mädchen", 
      phonetic: "/ˈmɛːtçən/", 
      meaning: "girl", 
      cat: "Umlaute", 
      syllables: ["Mäd", "chen"], 
      hint: "<span class=\"ph\">ä</span> = \"e\" in bed. <span class=\"ph\">ch</span> after e/i = soft palatal hiss, not \"k\" or \"sh\".",
      correction: `"medt" + soft-ch + "en". Stress: <span class="ph">MÄD-chen</span>.`,
      acceptableVariants: ["mädchen", "madchen", "medchen", "maedchen", "medhen"]
    },
    { 
      word: "Füße", 
      phonetic: "/ˈfyːsə/", 
      meaning: "feet", 
      cat: "Umlaute", 
      syllables: ["Fü", "ße"], 
      hint: "<span class=\"ph\">ü</span> = rounded ee. <span class=\"ph\">ß</span> = always double ss, never \"z\".",
      correction: `<span class="ph">FÜ</span> = "few" with round lips + sse = "seh". <span class="ph">FÜ-sse</span>.`,
      acceptableVariants: ["füße", "fusse", "fuße", "fysse", "fuse"]
    },
    { 
      word: "Brötchen", 
      phonetic: "/ˈbʁøːtçən/", 
      meaning: "bread roll", 
      cat: "Umlaute", 
      syllables: ["Brö", "tchen"], 
      hint: "German <span class=\"ph\">R</span> is uvular (throat). <span class=\"ph\">ö</span> = rounded e. <span class=\"ph\">ch</span> after ö = soft palatal.",
      correction: `Brö = "bruh" rounded + tchen = t + soft-ch + en. Throat-R not English R.`,
      acceptableVariants: ["brötchen", "brotchen", "broetchen", "bretchen", "brechten"]
    },
    // Category: CH-Laut
    { 
      word: "ich", 
      phonetic: "/ɪç/", 
      meaning: "I", 
      cat: "CH-Laut", 
      syllables: ["ich"], 
      hint: `<span class="ph">ch</span> after i/e/ä = soft palatal. Tongue near front roof, breathe out with wide grin. NOT "ick" or "ish".`,
      correction: `"ikh" with soft hiss. Practice: smile wide and breathe — that's your <span class="ph">ich-sound</span>.`,
      acceptableVariants: ["ich", "ikh", "ish", "ik", "ig"]
    },
    { 
      word: "Buch", 
      phonetic: "/buːx/", 
      meaning: "book", 
      cat: "CH-Laut", 
      syllables: ["Buch"], 
      hint: `<span class="ph">ch</span> after a/o/u = back-throat guttural (ach-Laut), like Scottish "loch".`,
      correction: `Bu = "boo" + guttural <span class="ph">ch</span>. Not "book" — no k sound!`,
      acceptableVariants: ["buch", "book", "buk", "buh", "bux"]
    },
    { 
      word: "Küche", 
      phonetic: "/ˈkYçə/", 
      meaning: "kitchen", 
      cat: "CH-Laut", 
      syllables: ["Kü", "che"], 
      hint: `<span class="ph">ü</span> = rounded ee. <span class="ph">ch</span> after ü = soft palatal. Final <span class="ph">e</span> = short "uh", not silent.`,
      correction: `Kü = "kee" round lips + che = soft-ch + "uh". <span class="ph">KÜ-che</span>.`,
      acceptableVariants: ["küche", "kuche", "kueche", "kiche"]
    },
    { 
      word: "Nacht", 
      phonetic: "/naxt/", 
      meaning: "night", 
      cat: "CH-Laut", 
      syllables: ["Nacht"], 
      hint: `After <span class="ph">a</span>, <span class="ph">ch</span> = deep guttural ach-sound. Final <span class="ph">t</span> must be pronounced — no silent consonants in German.`,
      correction: `Na = "nah" + guttural <span class="ph">cht</span> + crisp <span class="ph">t</span>. Not "Nock" or "Nax".`,
      acceptableVariants: ["nacht", "naxt", "nakt", "nox", "nahkt"]
    },
    // Category: R-Laut
    {
      word: "Regen",
      phonetic: "/ˈʁeːɡən/",
      meaning: "rain",
      cat: "R-Laut",
      syllables: ["Re", "gen"],
      hint: `German <span class="ph">R</span> at word start = uvular (gargling gently). NOT English tongue-tip R. <span class="ph">G</span> = hard like "get".`,
      correction: `Throat-R + e = "ay" + gen. Try "hhh" in throat then add vowel. <span class="ph">REY-gen</span>.`,
      acceptableVariants: ["regen", "raygen", "rregen", "reegen"]
    },
    {
      word: "sprechen",
      phonetic: "/ˈʃpʁɛçən/",
      meaning: "to speak",
      cat: "R-Laut",
      syllables: ["spre", "chen"],
      hint: `<span class="ph">sp</span> at start = "shp" in German. <span class="ph">R</span> is uvular. <span class="ph">ch</span> after e = soft palatal.`,
      correction: `sp → shp + throat-R + e = "eh" + soft-ch + en. <span class="ph">SHPRE-chen</span>.`,
      acceptableVariants: ["sprechen", "shprechen", "sprechon", "schprechen"]
    },
    {
      word: "Wörter",
      phonetic: "/ˈvœʁtɐ/",
      meaning: "words",
      cat: "R-Laut",
      syllables: ["Wör", "ter"],
      hint: `<span class="ph">W</span> = English "V". <span class="ph">ö</span> = rounded e. Final <span class="ph">er</span> = schwa "uh" — R nearly silent.`,
      correction: `W → V + ör = rounded-er + ter = "tuh". <span class="ph">VÖR-tuh</span>.`,
      acceptableVariants: ["wörter", "vörter", "worter", "vurter", "vurta", "vorter"]
    },
    {
      word: "Straße",
      phonetic: "/ˈʃtʁaːsə/",
      meaning: "street",
      cat: "R-Laut",
      syllables: ["Stra", "ße"],
      hint: `<span class="ph">st</span> at start = "sht". <span class="ph">ß</span> = double ss voiceless. <span class="ph">a</span> = long "ah".`,
      correction: `St → sht + throat-R + a = long-ah + ße = ssuh. <span class="ph">SHTRAH-sse</span>.`,
      acceptableVariants: ["straße", "strasse", "shtrase", "strase", "strasa"]
    },
    // Category: Vokale
    {
      word: "stehen",
      phonetic: "/ˈʃteːən/",
      meaning: "to stand",
      cat: "Vokale",
      syllables: ["ste", "hen"],
      hint: `<span class="ph">st</span> = "sht". <span class="ph">e</span> before h = long "ay". Silent <span class="ph">h</span> just lengthens vowel. Final <span class="ph">en</span> = "en".`,
      correction: `sht + long-e = "shtay" + hen. <span class="ph">SHTAY-en</span>.`,
      acceptableVariants: ["stehen", "shtehen", "stayen", "stayan", "shtayen", "stehn"]
    },
    {
      word: "Zwiebel",
      phonetic: "/tsviːbəl/",
      meaning: "onion",
      cat: "Vokale",
      syllables: ["Zwie", "bel"],
      hint: `<span class="ph">Z</span> = "ts" like pizza. <span class="ph">ie</span> = long "ee". <span class="ph">W</span> = "v". Starts with ts-v not "zw".`,
      correction: `Z = ts + w = v + ie = ee + bel = "bul". <span class="ph">TSVEE-bul</span>. Not "Zwibble".`,
      acceptableVariants: ["zwiebel", "tsvibel", "tsveebl", "zwibel", "tsveebell", "zviebel"]
    },
    {
      word: "Boot",
      phonetic: "/boːt/",
      meaning: "boat",
      cat: "Vokale",
      syllables: ["Boot"],
      hint: `Double <span class="ph">oo</span> = long "oh" (not "oo" in book). Final <span class="ph">t</span> clearly pronounced.`,
      correction: `B + long-oo = "boh" + crisp t. <span class="ph">BOHT</span>. Longer than English "boat".`,
      acceptableVariants: ["boot", "boat", "boht", "bote", "bout", "bot"]
    },
    {
      word: "eigentlich",
      phonetic: "/ˈaɪ̯ɡn̩tlɪç/",
      meaning: "actually",
      cat: "Vokale",
      syllables: ["ei", "gent", "lich"],
      hint: `<span class="ph">ei</span> = "eye" sound. <span class="ph">g</span> = hard g. Final <span class="ph">ch</span> after i = soft palatal. Stress: <span class="ph">EI-gent-lich</span>.`,
      correction: `ei = eye + gent = gent + lich = likh (soft ch). <span class="ph">EYE-gent-likh</span>.`,
      acceptableVariants: ["eigentlich", "eigentlikh", "eigentlik", "eygentlich", "aygentlich"]
    },
    {
      word: "kaufen",
      phonetic: "/ˈkaʊ̯fən/",
      meaning: "to buy",
      cat: "Vokale",
      syllables: ["kau", "fen"],
      hint: `<span class="ph">au</span> = "ow" as in "cow" — diphthong gliding from ah to oo. Final <span class="ph">en</span> = "en".`,
      correction: `k + au = "kow" (rhymes cow) + fen = "fen". <span class="ph">KOW-fen</span>.`,
      acceptableVariants: ["kaufen", "kowfen", "kauven", "cowfen", "kaufn"]
    },
    // Category: Konsonanten
    {
      word: "Vater",
      phonetic: "/ˈfaːtɐ/",
      meaning: "father",
      cat: "Konsonanten",
      syllables: ["Va", "ter"],
      hint: `<span class="ph">V</span> = "F" in native German words. Final <span class="ph">er</span> = schwa "uh".`,
      correction: `V → f + a = long-ah + ter = "tuh". <span class="ph">FAH-tuh</span>. Not English V!`,
      acceptableVariants: ["vater", "fater", "father", "fahter", "fata", "fahtuh"]
    },
    {
      word: "Wasser",
      phonetic: "/ˈvasɐ/",
      meaning: "water",
      cat: "Konsonanten",
      syllables: ["Was", "ser"],
      hint: `<span class="ph">W</span> = "V". <span class="ph">ss</span> = sharp voiceless s. Final <span class="ph">er</span> = schwa.`,
      correction: `W → v + as = "ahss" + ser = "suh". <span class="ph">VAHSS-uh</span>.`,
      acceptableVariants: ["wasser", "vasser", "vaser", "waser", "vassr", "vassa"]
    },
    {
      word: "Pferd",
      phonetic: "/pfɛʁt/",
      meaning: "horse",
      cat: "Konsonanten",
      syllables: ["Pferd"],
      hint: `<span class="ph">Pf</span> = BOTH p AND f pronounced together — no silent letters in German!`,
      correction: `Pf = aspirated pf + er = "ehr" + d devoiced to t. <span class="ph">PFEHRT</span>.`,
      acceptableVariants: ["pferd", "pfehrt", "ferd", "pfert", "pherd", "pfeerd"]
    },
    {
      word: "jung",
      phonetic: "/jʊŋ/",
      meaning: "young",
      cat: "Konsonanten",
      syllables: ["jung"],
      hint: `<span class="ph">j</span> = English "Y" like "yes". <span class="ph">ng</span> = same as "sing" — no hard G at end.`,
      correction: `j → y + u = short-oo + ng. <span class="ph">YOONG</span>. Not English J!`,
      acceptableVariants: ["jung", "yung", "young", "yoong", "junge"]
    },
    {
      word: "Zug",
      phonetic: "/tsuːk/",
      meaning: "train",
      cat: "Konsonanten",
      syllables: ["Zug"],
      hint: `<span class="ph">Z</span> = "ts" like "cats". Final <span class="ph">g</span> devoiced → sounds like k.`,
      correction: `Z → ts + u = long-oo + g devoiced → k. <span class="ph">TSOOK</span>. Not English Z!`,
      acceptableVariants: ["zug", "tsoog", "tsuk", "tzug", "tsook", "zoog"]
    },
    // Category: Sätze (Phrases)
    {
      word: "Wie geht's?",
      phonetic: "/viː ɡeːts/",
      meaning: "How are you?",
      cat: "Sätze",
      syllables: ["Wie", "geht's"],
      hint: `<span class="ph">W</span> = v. <span class="ph">ie</span> = long ee. <span class="ph">geht</span> = gayt. <span class="ph">'s</span> = short s.`,
      correction: `Wie = vee + geht's = gayts. <span class="ph">VEE GAYTS?</span>`,
      acceptableVariants: ["wie geht's", "wie gehts", "vee gayts", "wie geht", "vi gets"]
    },
    {
      word: "Entschuldigung",
      phonetic: "/ɛntˈʃʊldɪɡʊŋ/",
      meaning: "excuse me",
      cat: "Sätze",
      syllables: ["Ent", "schul", "di", "gung"],
      hint: `<span class="ph">sch</span> = sh. Stress on second syllable: ent-SCHUL-di-gung.`,
      correction: `Ent=ent + schul=shool + di=dee + gung=goong. <span class="ph">ent-SHOOL-dee-goong</span>.`,
      acceptableVariants: ["entschuldigung", "entshuldigung", "entschuldgung", "enshuldigung"]
    },
    {
      word: "Guten Morgen",
      phonetic: "/ˈɡuːtən ˈmɔʁɡən/",
      meaning: "Good morning",
      cat: "Sätze",
      syllables: ["Gu", "ten", "Mor", "gen"],
      hint: `<span class="ph">G</span> = hard g. <span class="ph">u</span> = long oo. Morgen has throat-R, stress first syllable.`,
      correction: `Guten = GOO-ten + Morgen = MOR-gen (throat R). <span class="ph">GOO-ten MOR-gen</span>.`,
      acceptableVariants: ["guten morgen", "gooten morgen", "guten morgan", "gooten morgan"]
    }
  ];

  let currentCategory = "Alle";
  let filteredWords = [];
  let currentIdx = 0;
  let stats = { correct: 0, wrong: 0, streak: 0, history: [] };
  let answered = []; // Track results for each word in filteredWords
  let recording = false;
  let recognition = null;

  function similarity(s1, s2) {
    let longer = s1;
    let shorter = s2;
    if (s1.length < s2.length) {
      longer = s2;
      shorter = s1;
    }
    const longerLength = longer.length;
    if (longerLength === 0) return 1.0;
    return (longerLength - editDistance(longer, shorter)) / parseFloat(longerLength);
  }

  function editDistance(s1, s2) {
    s1 = s1.toLowerCase();
    s2 = s2.toLowerCase();
    const costs = [];
    for (let i = 0; i <= s1.length; i++) {
      let lastValue = i;
      for (let j = 0; j <= s2.length; j++) {
        if (i === 0) costs[j] = j;
        else {
          if (j > 0) {
            let newValue = costs[j - 1];
            if (s1.charAt(i - 1) !== s2.charAt(j - 1)) {
              newValue = Math.min(Math.min(newValue, lastValue), costs[j]) + 1;
            }
            costs[j - 1] = lastValue;
            lastValue = newValue;
          }
        }
      }
      if (i > 0) costs[s2.length] = lastValue;
    }
    return costs[s2.length];
  }

  function setupRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return;
    recognition = new SpeechRecognition();
    recognition.lang = "de-DE";
    recognition.maxAlternatives = 5;
    recognition.interimResults = false;

    recognition.onresult = (event) => {
      const alternatives = Array.from(event.results[0]);
      processSpeechResults(alternatives);
    };

    recognition.onerror = (event) => {
      console.error("Speech recognition error", event.error);
      stopRecording();
      micStatus.textContent = "Fehler: " + event.error;
    };

    recognition.onend = () => {
      if (recording) stopRecording();
    };
  }

  function init() {
    setupRecognition();
    filterWords();
    renderWord();
    updateStats();
  }

  function filterWords() {
    if (currentCategory === "Alle") {
      filteredWords = [...GERMAN_WORDS];
    } else {
      filteredWords = GERMAN_WORDS.filter(w => w.cat === currentCategory);
    }
    currentIdx = 0;
    answered = new Array(filteredWords.length).fill(null);
  }

  function renderWord() {
    if (currentIdx >= filteredWords.length) {
      showCompletion();
      return;
    }
    const word = filteredWords[currentIdx];
    targetWord.textContent = word.word;
    ipaText.textContent = word.phonetic || word.ipa;
    meaningText.textContent = word.meaning;
    hintContent.innerHTML = word.hint;
    topicChip.textContent = word.cat === "Alle" ? "All" : 
                             word.cat === "Umlaute" ? "Umlauts" :
                             word.cat === "CH-Laut" ? "CH-Sound" :
                             word.cat === "R-Laut" ? "R-Sound" :
                             word.cat === "Vokale" ? "Vowels" :
                             word.cat === "Konsonanten" ? "Consonants" :
                             word.cat === "Sätze" ? "Phrases" : word.cat;
    questionNum.textContent = `#${currentIdx + 1}`;
    
    progressText.textContent = `Question ${currentIdx + 1} of ${filteredWords.length}`;
    const progress = (currentIdx / filteredWords.length) * 100;
    progressFill.style.width = `${progress}%`;
    
    if (answered[currentIdx]) {
      showResult(answered[currentIdx], true);
    } else {
      resultPanel.hidden = true;
    }
    
    quizCard.hidden = false;
    completionScreen.hidden = true;
  }

  function updateStats() {
    correctCountEl.textContent = stats.correct;
    wrongCountEl.textContent = stats.wrong;
    streakCountEl.textContent = stats.streak;
    
    const total = stats.correct + stats.wrong;
    const score = total === 0 ? 0 : Math.round((stats.correct / total) * 100);
    scorePill.textContent = `${score}%`;

    // Also update progress bar if we want it to be synced with stats
    if (filteredWords.length > 0) {
      const progress = (currentIdx / filteredWords.length) * 100;
      progressFill.style.width = `${progress}%`;
    }
  }

  async function startRecording() {
    if (recording) return;
    if (!recognition) {
      micStatus.textContent = "Browser unterstützt keine Spracherkennung";
      return;
    }
    recording = true;
    
    micStatus.textContent = "Aufnahme...";
    micAnimations.hidden = false;
    micZone.classList.add("micActive");
    recBtn.textContent = "⏹️ Stoppen";
    
    try {
      recognition.start();
    } catch (e) {
      console.error(e);
      stopRecording();
    }
  }

  function stopRecording() {
    if (!recording) return;
    recording = false;
    if (recognition) recognition.stop();
    
    micAnimations.hidden = true;
    micZone.classList.remove("micActive");
    micStatus.textContent = "Analysieren...";
    recBtn.textContent = "🎙️ Aufnehmen";
  }

  function processSpeechResults(alternatives) {
    const word = filteredWords[currentIdx];
    let bestScore = 0;
    let bestTranscript = "";

    alternatives.forEach(alt => {
      const transcript = alt.transcript.toLowerCase().trim();
      
      // Check word directly
      const s1 = similarity(transcript, word.word.toLowerCase());
      if (s1 > bestScore) {
        bestScore = s1;
        bestTranscript = transcript;
      }

      // Check acceptable variants
      if (word.acceptableVariants) {
        word.acceptableVariants.forEach(v => {
          const s2 = similarity(transcript, v.toLowerCase());
          if (s2 > bestScore) {
            bestScore = s2;
            bestTranscript = transcript;
          }
        });
      }
    });

    let status = "WRONG";
    if (bestScore > 0.75) status = "CORRECT";
    else if (bestScore > 0.55) status = "CLOSE";

    const result = {
      status: status,
      score: bestScore * 100,
      transcript: bestTranscript || "...",
      word: word
    };

    answered[currentIdx] = result;
    showResult(result);
  }

  function showResult(result, isReview = false) {
    resultPanel.hidden = false;
    resultPanel.classList.add("fadeIn");
    transcriptText.textContent = result.transcript;
    
    const status = result.status;
    const word = result.word;
    const transcript = (result.transcript || "").toLowerCase();
    
    if (status === "CORRECT") {
      resultIcon.textContent = "✅";
      resultTitle.textContent = "Excellent! Perfect pronunciation! 🎉";
      if (!isReview) {
        stats.correct++;
        stats.streak++;
      }
    } else if (status === "CLOSE") {
      resultIcon.textContent = "⚠️";
      resultTitle.textContent = "Almost right! Just a bit more practice!";
      if (!isReview) {
        stats.wrong++;
        stats.streak = 0;
      }
    } else {
      resultIcon.textContent = "❌";
      resultTitle.textContent = "Not quite — let's practice this!";
      if (!isReview) {
        stats.wrong++;
        stats.streak = 0;
      }
    }
    
    updateStats();
    
    // Syllable Chips
    syllableChips.innerHTML = "";
    word.syllables.forEach(s => {
      const chip = document.createElement("span");
      chip.className = "syllablePill";
      
      if (status === "CORRECT") {
        chip.classList.add("pillGood");
      } else if (status === "CLOSE") {
        // Mixed logic: check if syllable is somewhat present in transcript
        if (transcript.includes(s.toLowerCase())) {
          chip.classList.add("pillGood");
        } else {
          chip.classList.add("pillBad");
        }
      } else {
        chip.classList.add("pillBad");
      }
      
      chip.textContent = s;
      syllableChips.appendChild(chip);
    });
    
    // Correction Box
    if (status !== "CORRECT") {
      correctionBox.hidden = false;
      correctionGuide.innerHTML = word.correction || `Try: <span class='goldSerif'>${word.word}</span> <br> <span class='blueMonospace'>${word.phonetic || word.ipa}</span>`;
    } else {
      correctionBox.hidden = true;
    }
    
    // AI Feedback
    if (!isReview) {
      aiLoading.hidden = false;
      aiFeedback.textContent = "";
      setTimeout(() => {
        aiLoading.hidden = true;
        // Simulating AI feedback based on status
        if (status === "CORRECT") {
          aiFeedback.textContent = "Excellent pronunciation! You hit the phonemes perfectly and kept the rhythm.";
        } else if (status === "CLOSE") {
          aiFeedback.textContent = "Already very recognizable. Focus especially on the highlighted syllables and mouth position.";
        } else {
          aiFeedback.textContent = "Don't worry, that was a tricky word. Check the tip above and try again slowly.";
        }
      }, 1200);
    } else {
      aiLoading.hidden = true;
      aiFeedback.textContent = "Result from your session saved.";
    }
  }

  function showCompletion() {
    quizCard.hidden = true;
    completionScreen.hidden = false;
    completionScreen.classList.add("fadeIn");
    
    const total = stats.correct + stats.wrong;
    const score = total === 0 ? 0 : Math.round((stats.correct / total) * 100);
    
    let grade = "D";
    let title = "Don't give up!";
    let msg = "Try again — practice makes perfect!";
    let color = "var(--red)";

    if (score >= 90) {
      grade = "A";
      title = "Wonderful!";
      msg = "You sound like a native speaker! 🌟";
      color = "var(--green)";
    } else if (score >= 75) {
      grade = "B";
      title = "Very good!";
      msg = "Great work — keep polishing those tricky sounds!";
      color = "var(--blue)";
    } else if (score >= 55) {
      grade = "C";
      title = "Well done!";
      msg = "A bit more practice with umlauts and ch-sounds!";
      color = "var(--accent)";
    }
    
    gradeVal.textContent = grade;
    gradeVal.style.background = "none";
    gradeVal.style.webkitTextFillColor = color;
    gradeVal.style.color = color;
    
    document.getElementById("completionTitle").textContent = title;
    document.getElementById("completionMsg").textContent = msg;
  }

  // Event Listeners
  categoryTabs.addEventListener("click", (e) => {
    if (e.target.classList.contains("tabBtn")) {
      document.querySelectorAll(".tabBtn").forEach(b => b.classList.remove("active"));
      e.target.classList.add("active");
      currentCategory = e.target.dataset.cat;
      stats.correct = 0;
      stats.wrong = 0;
      stats.streak = 0;
      filterWords();
      renderWord();
      updateStats();
    }
  });

  micZone.addEventListener("click", () => {
    if (recording) stopRecording();
    else startRecording();
  });

  recBtn.addEventListener("click", () => {
    if (recording) stopRecording();
    else startRecording();
  });

  listenBtn.addEventListener("click", () => {
    const word = filteredWords[currentIdx].word;
    const utterance = new SpeechSynthesisUtterance(word);
    utterance.lang = "de-DE";
    utterance.rate = 0.82;
    
    const voices = window.speechSynthesis.getVoices();
    const germanVoice = voices.find(v => v.lang.startsWith("de"));
    if (germanVoice) utterance.voice = germanVoice;
    
    window.speechSynthesis.speak(utterance);
  });

  targetWord.addEventListener("click", () => listenBtn.click());

  skipBtn.addEventListener("click", () => {
    const word = filteredWords[currentIdx];
    const result = {
      status: "WRONG",
      score: 0,
      transcript: "Übersprungen",
      word: word
    };
    answered[currentIdx] = result;
    stats.wrong++;
    stats.streak = 0;
    updateStats();
    currentIdx++;
    renderWord();
  });

  nextBtn.addEventListener("click", () => {
    currentIdx++;
    renderWord();
  });

  prevBtn.addEventListener("click", () => {
    if (currentIdx > 0) {
      currentIdx--;
      renderWord();
    }
  });

  restartBtn.addEventListener("click", () => {
    stats.correct = 0;
    stats.wrong = 0;
    stats.streak = 0;
    filterWords(); // This already resets answered
    renderWord();
    updateStats();
  });

  init();
})();
