// Presentation layer for the browser version.
// Keeps the reaction pane empty when no gesture is active, adds subtle
// transitions, configurable timing, and prevents immediate meme repeats.

const MEOW_UI = {
  // The detector already requires 5 consecutive frames internally.
  // These values control the presentation layer around that detector.
  showDelayMs: 0,
  hideDelayMs: 600,
  fadeInMs: 120,
  fadeOutMs: 180,
  avoidImmediateRepeat: true,
};

const MEOW_MEMES = {
  rockstar: ["memes/cat.jpg"],
  oneFingerUp: ["memes/profcat.jpg", "memes/professorcat.jpg"],
  fist: ["memes/punchcat.jpg"],
  shhh: ["memes/shhcat.jpg"],
  twoFingersTogether: [
    "memes/uwucat.jpg",
    "memes/uwucatt.jpg",
    "memes/fingers together muehehe .jpg",
  ],
  handCoverFace: ["memes/hand cover face .jpg"],
  crashOutCat: ["memes/crashout cat .jpg"],
  twoHandsOnHead: ["memes/two hands on head .jpg"],
  handStretchedOut: ["memes/hand stretched out, palm facing up .jpg"],
  sideEyeCat: ["memes/side eye cat.jpg"],
};

const memeImg = document.getElementById("memeImg");
let lastShownSrc = "";
let lastObservedSrc = null;
let hideTimer = null;
let showTimer = null;

function fileNameForSrc(src) {
  return decodeURIComponent(src.split("/").pop() || "");
}

function gestureFromSrc(src) {
  const file = fileNameForSrc(src);
  for (const [gesture, files] of Object.entries(MEOW_MEMES)) {
    if (files.some((candidate) => candidate.endsWith(file))) return gesture;
  }
  return null;
}

function pickNonRepeating(src) {
  if (!MEOW_UI.avoidImmediateRepeat) return src;

  const gesture = gestureFromSrc(src);
  if (!gesture) return src;

  const options = MEOW_MEMES[gesture];
  if (options.length < 2 || !src.endsWith(lastShownSrc)) return src;

  const alternatives = options.filter((candidate) => !candidate.endsWith(lastShownSrc));
  return alternatives[Math.floor(Math.random() * alternatives.length)] || src;
}

function setHidden() {
  clearTimeout(showTimer);
  memeImg.classList.remove("meme-visible");
  memeImg.classList.add("meme-hidden");
  memeImg.style.opacity = "0";
}

function showMeme(src) {
  clearTimeout(hideTimer);
  clearTimeout(showTimer);

  const chosen = pickNonRepeating(src);
  lastShownSrc = chosen.split("/").pop() || "";

  const reveal = () => {
    memeImg.src = chosen;
    memeImg.classList.remove("meme-hidden");
    memeImg.classList.add("meme-visible");
    memeImg.style.opacity = "1";
  };

  if (MEOW_UI.showDelayMs > 0) {
    showTimer = setTimeout(reveal, MEOW_UI.showDelayMs);
  } else {
    reveal();
  }
}

function hideMeme() {
  clearTimeout(showTimer);
  clearTimeout(hideTimer);

  memeImg.classList.remove("meme-visible");
  memeImg.classList.add("meme-hidden");
  memeImg.style.opacity = "0";

  hideTimer = setTimeout(() => {
    memeImg.removeAttribute("src");
  }, MEOW_UI.fadeOutMs);
}

function syncFromDetector() {
  const src = memeImg.getAttribute("src") || "";
  if (src === lastObservedSrc) return;
  lastObservedSrc = src;

  if (!src || src.endsWith("/pokercat.jpg") || src === "memes/pokercat.jpg") {
    hideMeme();
    return;
  }

  showMeme(src);
}

const style = document.createElement("style");
style.textContent = `
  #memeImg {
    opacity: 0;
    transition: opacity ${MEOW_UI.fadeInMs}ms ease, visibility ${MEOW_UI.fadeOutMs}ms ease;
    visibility: hidden;
  }
  #memeImg.meme-visible {
    visibility: visible;
  }
  #memeImg.meme-hidden {
    visibility: hidden;
  }
`;
document.head.appendChild(style);

setHidden();

new MutationObserver(syncFromDetector).observe(memeImg, {
  attributes: true,
  attributeFilter: ["src"],
});

// Presentation-only fallback; no detection work is performed here.
setInterval(syncFromDetector, 100);
