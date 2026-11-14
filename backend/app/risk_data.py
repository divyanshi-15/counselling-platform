"""SYNTHETIC, hand-written phrases for the layer-2 risk classifier. Demonstration only; not clinically validated."""

POSITIVE = [
    # English (direct + indirect)
    "I want to end my life",
    "I feel like I can't go on",
    "I am going to hurt myself tonight",
    "everyone would be better off without me",
    "I don't see the point in being alive anymore",
    "I keep thinking about not waking up tomorrow",
    "I have been thinking about ways to end things",
    "I wish I could just disappear and never come back",
    "I have been cutting myself again",
    "I can't take this anymore and want it all to stop for good",
    # Hindi native + romanised
    "मैं मरना चाहता हूँ",
    "मुझे जीने का मन नहीं है",
    "मैं सब कुछ खत्म कर देना चाहता हूँ",
    "मेरे बिना सब लोग ठीक रहेंगे",
    "अब जीने का कोई मतलब नहीं रहा",
    "मैं खुद को नुकसान पहुँचाना चाहती हूँ",
    "मैं खुदकुशी करने के बारे में सोच रहा हूँ",
    "main marna chahta hoon",
    "ab jeene ka koi matlab nahi hai",
    "main apni jaan le loonga",
    # Kannada native + romanised
    "ನಾನು ಸಾಯಬೇಕು ಅನಿಸುತ್ತಿದೆ",
    "ಬದುಕಲು ಇಷ್ಟವಿಲ್ಲ",
    "ನನ್ನ ಜೀವ ಕೊನೆಗೊಳಿಸಬೇಕು ಅನಿಸುತ್ತದೆ",
    "ನಾನು ಇಲ್ಲದಿದ್ದರೆ ಎಲ್ಲರಿಗೂ ಒಳ್ಳೆಯದು",
    "ಇನ್ನು ಬದುಕಿ ಏನು ಪ್ರಯೋಜನ",
    "ನಾನು ಆತ್ಮಹತ್ಯೆ ಮಾಡಿಕೊಳ್ಳುತ್ತೇನೆ",
    "ನನಗೆ ನೋವು ಮಾಡಿಕೊಳ್ಳಬೇಕು ಅನಿಸುತ್ತದೆ",
    "naanu saayabeku anisuttide",
    "badukalu ishta illa",
    "nanna jeeva mugisabeku",
]

NEGATIVE = [
    # English, including hard negatives (idioms / figurative speech)
    "this deadline is killing me",
    "I am dying to try the new cafe",
    "I killed it in my presentation today",
    "my phone died halfway through the day",
    "I want a thought record for my work anxiety",
    "I slept badly and feel tired",
    "I am worried about my exams next week",
    "I want to stop overthinking at night",
    "we practised slow breathing this week",
    "I could kill for a cup of chai",
    # Hindi
    "मुझे रात को नींद नहीं आती",
    "मैं परीक्षा को लेकर चिंतित हूँ",
    "यह गर्मी मुझे मार डालेगी",
    "मैं साँस की एक्सरसाइज़ करना चाहता हूँ",
    "मैं हँसते-हँसते मर गया यार",
    "मैं आज बहुत थका हुआ हूँ",
    "mujhe kaam ka bahut tension hai",
    "is hafte maine roz walk kiya",
    "mera phone mar gaya hai",
    "mujhe thoda ghabrahat ho rahi hai",
    # Kannada
    "ನನಗೆ ರಾತ್ರಿ ನಿದ್ರೆ ಬರುವುದಿಲ್ಲ",
    "ಈ ವಾರ ಕೆಲಸದ ಒತ್ತಡ ಜಾಸ್ತಿ ಇದೆ",
    "ನಾನು ಉಸಿರಾಟದ ವ್ಯಾಯಾಮ ಮಾಡಲು ಬಯಸುತ್ತೇನೆ",
    "ನನಗೆ ತುಂಬಾ ಚಿಂತೆ ಆಗುತ್ತಿದೆ ಆದರೆ ನಾನು ಸುರಕ್ಷಿತವಾಗಿದ್ದೇನೆ",
    "ಈ ಡೆಡ್‌ಲೈನ್ ನನ್ನ ಪ್ರಾಣ ತಿನ್ನುತ್ತಿದೆ",
    "ನಾನು ಇಂದು ಬೆಳಿಗ್ಗೆ ವಾಕಿಂಗ್ ಹೋಗಿದ್ದೆ",
    "ನಾನು ಸಾಯುವಷ್ಟು ಹಸಿದಿದ್ದೇನೆ",
    "naanige ratri nidre barolla",
    "ee vaara kelasada ottada jaasti ide",
    "nanage swalpa chinte aagide",
]


# Benign phrases with risk-like words. Layer 1 must never fire on these (asserted in tests);
# layer 2 behaviour on them is reported, not asserted (see README).
HARD_NEGATIVES_15 = [
    "I'm dying to see my friends", "this homework is killing me", "I want to end this task quickly",
    "I could murder a pizza right now", "my phone battery is dead", "that joke killed me, I laughed so hard",
    "I'm dead tired after the commute", "we need to kill the old meeting series", "I want to cut my screen time",
    "this traffic is the death of me", "I'm starving to death, let's eat", "I'd die of embarrassment if I forgot my lines",
    "she is killing it at her new job", "I want to end the call early, I have class", "the batteries died during the exam",
]
