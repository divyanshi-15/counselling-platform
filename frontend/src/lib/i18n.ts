import { useAuth } from "./auth";

const en = {
  space: "My skill-building space",
  checkin: "Daily check-in", checkinHint: "How are you feeling today, and how did you sleep?",
  journal: "Journal", journalHint: "Private notes. Only you can see them unless you choose to share one.",
  journeys: "Journeys", journeysHint: "Step-by-step programmes from your therapist.",
  insights: "Insights", insightsHint: "Your mood, sleep and exercises over the last 30 days.",
  reminders: "Reminders", remindersHint: "Gentle nudges by email. Off unless you turn them on.",
  open: "Open", back: "Back to my space",
  mood: "Mood", moodScale: "1 is low, 5 is good", sleepHours: "Hours slept", note: "Note (optional)",
  save: "Save", saving: "Saving…", saved: "Saved. Thank you for checking in.", updateToday: "Update today's check-in",
  alreadyToday: "You checked in today. You can change it below.",
  writeEntry: "Write an entry", shareWithTherapist: "Share this entry with my therapist",
  shared: "Shared with therapist", private: "Private", share: "Share", unshare: "Make private",
  noEntries: "No entries yet.", saveEntry: "Save entry",
  week: "Week", thisWeek: "This week", steps: "steps", done: "Done", markDone: "Mark as done",
  progress: "Progress", noJourneys: "No programme yet. Your therapist can assign one.", exercise: "Exercise",
  moodChart: "Mood (1-5)", sleepChart: "Sleep (hours)", exerciseChart: "Exercises completed",
  checkins: "Check-ins", avgMood: "Average mood", avgSleep: "Average sleep (h)", exercisesDone: "Exercises completed",
  exercisesAssigned: "Exercises assigned", noData: "No check-ins yet. Your charts will appear here.", date: "Date",
  remDaily: "Daily check-in reminder", remNudge: "Reminders about exercises from my therapist",
  remOff: "Off", remOn: "On", remNote: "Sent by email at most once a day. You can switch these off at any time.",
} as const;
export type Key = keyof typeof en;

const hi: Record<Key, string> = {
  space: "मेरा कौशल-निर्माण स्पेस",
  checkin: "दैनिक चेक-इन", checkinHint: "आज आप कैसा महसूस कर रहे हैं, और नींद कैसी रही?",
  journal: "जर्नल", journalHint: "निजी नोट्स। जब तक आप साझा करना न चुनें, केवल आप इन्हें देख सकते हैं।",
  journeys: "यात्राएँ", journeysHint: "आपके थेरेपिस्ट के चरण-दर-चरण कार्यक्रम।",
  insights: "अंतर्दृष्टि", insightsHint: "पिछले 30 दिनों में आपका मूड, नींद और अभ्यास।",
  reminders: "रिमाइंडर", remindersHint: "ईमेल से हल्के अनुस्मारक। जब तक आप चालू न करें, बंद रहते हैं।",
  open: "खोलें", back: "मेरे स्पेस पर वापस",
  mood: "मूड", moodScale: "1 कम है, 5 अच्छा है", sleepHours: "सोने के घंटे", note: "नोट (वैकल्पिक)",
  save: "सहेजें", saving: "सहेजा जा रहा है…", saved: "सहेज लिया गया। चेक-इन करने के लिए धन्यवाद।", updateToday: "आज का चेक-इन बदलें",
  alreadyToday: "आपने आज चेक-इन कर लिया है। आप इसे नीचे बदल सकते हैं।",
  writeEntry: "प्रविष्टि लिखें", shareWithTherapist: "यह प्रविष्टि मेरे थेरेपिस्ट के साथ साझा करें",
  shared: "थेरेपिस्ट के साथ साझा", private: "निजी", share: "साझा करें", unshare: "निजी करें",
  noEntries: "अभी कोई प्रविष्टि नहीं।", saveEntry: "प्रविष्टि सहेजें",
  week: "सप्ताह", thisWeek: "इस सप्ताह", steps: "चरण", done: "पूरा", markDone: "पूरा हुआ चिह्नित करें",
  progress: "प्रगति", noJourneys: "अभी कोई कार्यक्रम नहीं। आपके थेरेपिस्ट एक दे सकते हैं।", exercise: "अभ्यास",
  moodChart: "मूड (1-5)", sleepChart: "नींद (घंटे)", exerciseChart: "पूरे किए गए अभ्यास",
  checkins: "चेक-इन", avgMood: "औसत मूड", avgSleep: "औसत नींद (घंटे)", exercisesDone: "पूरे किए गए अभ्यास",
  exercisesAssigned: "दिए गए अभ्यास", noData: "अभी कोई चेक-इन नहीं। आपके चार्ट यहाँ दिखेंगे।", date: "तारीख",
  remDaily: "दैनिक चेक-इन रिमाइंडर", remNudge: "थेरेपिस्ट के दिए अभ्यासों के रिमाइंडर",
  remOff: "बंद", remOn: "चालू", remNote: "ईमेल से दिन में अधिकतम एक बार। आप इन्हें कभी भी बंद कर सकते हैं।",
};

export const STRINGS = { en, hi };

export function useLang(): "en" | "hi" {
  const { user } = useAuth();
  return user?.language === "hi" ? "hi" : "en";
}

export function useT() {
  const lang = useLang();
  return (k: Key): string => STRINGS[lang][k];
}
