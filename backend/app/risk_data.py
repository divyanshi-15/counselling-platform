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
    "I want to take my own life",
    "I have a plan to kill myself",
    "I don't want to be alive anymore",
    "I think about suicide a lot",
    "I feel like ending it all tonight",
    "मैं अपनी जान लेना चाहता हूँ",
    "मुझे लगता है कि मुझे मर जाना चाहिए",
    "मैं खुदकुशी करना चाहती हूँ",
    "mujhe jeene ka mann nahi karta",
    "main zindagi khatam kar dena chahta hoon",
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
    "mujhe interview se pehle ghabrahat hai",
    "I had a stressful day but I am safe",
    "I want to book a session next week",
    "I need help planning my study time",
    "my boss is driving me crazy this week",
    "मुझे कल की मीटिंग को लेकर घबराहट है",
    "मैं आज अपने दोस्तों से मिलने जा रहा हूँ",
    "मुझे अपनी नींद सुधारनी है",
    "mujhe kal ke exam ki chinta hai",
    "main aaj bahut thaka hua hoon",
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
