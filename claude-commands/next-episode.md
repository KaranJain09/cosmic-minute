---
description: Write and render new standalone space reels. Usage: /next-episode [count, default 2]
---

Make $ARGUMENTS new reel(s) (if no number was given, make 2: today's daily quota). Every reel stands alone:
a stranger who has never seen the channel must understand it and want to watch to the end.

## 1. Read the state
Read `CLAUDE.md`, `config.yaml` and `series_history.json`. The new reel's `episode_number` is the highest number + 1
(it is only an internal ID; never say it on screen or in narration). If the last entry has `status: "failed"` or
`"scripted"`, fix and render that one first.

## 2. Pick the topic (this decides the views)
Search the web first. Use this order and make the two daily reels different types (ideally one news/event + one evergreen):
1. **news**: a space story from the last 7 days that people are talking about (discovery, launch, mission milestone,
   new telescope image, asteroid, solar storm, record).
2. **event**: something people can see or follow in the next 14 days (meteor shower peak, eclipse, supermoon,
   planets lining up, aurora forecast, comet, big launch). Give the exact date and the best time to look.
3. **evergreen**: a jaw-dropping fact with a fresh angle (black holes, the Sun, Moon, Mars, scale of the universe).

Rules:
- Verify every news or date claim in at least 2 reputable sources (NASA, ESA, ISRO, JPL, space.com, Sky & Telescope,
  timeanddate.com, major newspapers). Put the URLs in `sources`. Never invent or guess news. If it can't be verified,
  pick another topic.
- The reel is posted the next morning, so the story must still be true and relevant then.
- Never repeat a topic or angle already in `series_history.json`.
- Choose topics a 12-year-old can understand in one sentence. Skip anything that needs a diagram to explain.

## 3. Write the script (`scripts/episode_{N}.json`, schema in CLAUDE.md §3)

**Personality: space facts told by your funniest dost: backchodi, roasts, desi comparisons, savage one-liners.**
The facts are 100% real; the delivery is stand-up comedy. Think "Bhai, Venus toh toxic ex hai", "Mars pe plot lena
hai? Pehle oxygen ki EMI dekh lo", "Neutron star ka ek chammach = poore Mumbai ka traffic ka wazan".
- **Every reel has at least 3 laughs**: a roast of a planet/object/situation, a desi comparison (traffic, EMI, shaadi,
  rishtedaar, Sharma ji ka beta, cricket, chai, exams, salary, Bollywood clichés described in words), and a savage
  closing line. Jokes may be cheeky and double-meaning (adult humour like viral Indian meme pages), but never sexually
  explicit, never about caste, religion, gender identity, disability, real private people, or sexual violence.
- **Trend-jack**: search for this week's viral Indian Instagram/meme phrases and formats and fit one in when it is
  natural (e.g. a viral dialogue pattern). Use only the phrase or format idea, never copied video or audio.
- **Gaali**: mild slang is spoken openly (saala, bakchodi, pagal, bawaal, faad diya). Strong gaali goes inside
  double braces in BOTH narration and speech, e.g. `{{bhenchod}}` / `{{भेनचोद}}`: the voice says it, a TV beep covers
  it and captions show `#@$%!`. Max 2 bleeps per reel, never in the hook (scene 1 must be clean, so platforms push it).
- Never repeat a joke, roast or catchphrase that appears in recent scripts. Do not reuse "Sabse crazy part?" or
  "Haan ya naa?"; invent fresh lines every time.

**Language: Hinglish.** Every scene has two versions of the same line, with the SAME number of words:
- `narration`: Roman Hinglish, shown as captions. e.g. `"Bhai, socho... yeh kis cheez se bana hai?"`
- `speech`: the same words for the voice, Hindi words in Devanagari, English words in Latin letters, plus emotion
  tags in square brackets for the ElevenLabs v3 voice: `[excited]`, `[laughs]`, `[whispers]`, `[sarcastic]`,
  `[shocked]`, `[sighs]`, `[curious]`. Use 1-2 tags per scene where they help. Tags do not count as words and are
  removed automatically for the free backup voice.
  e.g. `"[laughs] भाई, सोचो... ये किस चीज़ से बना है?"`. Numbers as Hindi words in speech (सात सौ), digits only in on_screen_text.
- Keep science words people know in English (NASA, Mars, black hole, gravity, star, planet). Avoid shuddh Hindi
  ("antariksh", "grah") and avoid long English sentences. Punctuation drives emotion: use "!", "?" and "..." on purpose.
- `delivery` per scene (excited / curious / shock / serious / question / normal) still matters for the backup voice;
  vary it and never use the same delivery three scenes in a row.
- on_screen_text and title_card: short Roman Hinglish or English in capitals ("PAHAAD JITNA BHAARI", "SABSE CRAZY PART").
- Upload text in Hinglish (Roman letters), hashtags in English plus 2 Hindi-audience tags (#hindi #spacefactshindi).

**The first 2 seconds (most important):**
- Scene 1 = `role: "hook"`, max 8 words (Hinglish: 6-7, Hindi speech is slower), spoken in under 2.5 s. Lead with the single most shocking, specific claim.
  Patterns that work: a surprising number ("A day on Venus lasts longer than its year."), a threat or stake for the
  viewer ("You have 3 nights to see this."), breaking news ("NASA just found water where it shouldn't be."),
  a "you" scenario ("If you fell into Jupiter, this happens.").
- Never open with Yes/No/Maybe/So/Today/Hey/"Did you know"/"In this video", and never answer a previous reel.
- `title_card` = 2-4 BIG words that create curiosity (e.g. "IT'S SHRINKING", "3 NIGHTS LEFT"). It is readable
  on frame 1.
- Scene 1's picture must be the most striking image in the reel.

**Seconds 2-5:** scene 2 explains why it matters to the viewer and opens a loop ("and scientists can't explain why",
"but the scary part is the last one"). Pay that loop off near the end.

**The body:** one idea per scene, 4-11 words per scene, max 12 words per sentence. Plain everyday words, no jargon
(if a term is needed, explain it in 3 words). Compare to things people know: football fields, cars, the size of India,
a human lifetime. Every 2-3 scenes add a new surprise. No filler, no "basically", no "fun fact".

**The ending:** last scene `role: "cta"`: one easy question viewers can answer in a word or emoji
("Would you watch it? Yes or no?", "Which planet should be next?"). `cliffhanger_question` holds that question.
No "part 2", "next episode" or "follow for more" in narration (the pill on screen already says it).

**Numbers & limits:** 70-105 spoken words, 9-15 scenes, 25-40 s total. Write numbers the way they are spoken in
narration; put punchy numbers in `on_screen_text` with `*highlight*` and `count` motion. on_screen_text <= 5 words,
never a copy of the narration. Vary motion and camera every scene.

**Accuracy:** round, well-established figures; "about"/"scientists think" for estimates. Space facts must be correct.

**Extra fields:** `"angle": "news" | "event" | "evergreen"`, `"sources": ["https://..."]` (required for news/event).
`links_to_previous` is not needed. Titles never contain part or episode numbers.

**Upload text:** `youtube_title` = curiosity + keyword, under 70 characters, ends with #Shorts. `instagram_caption`
starts with the hook line, then 1-2 short lines, then the question. `pinned_comment` = the question with 2 answer
options. 8-12 hashtags: 3 topic-specific (e.g. #geminids), 3 trending-wide (#space #nasa #astronomy), rest niche.

**Visuals:** mix sources so it never looks like a slideshow:
- `"backend": "nasa"` with a concrete `query` for real space objects and missions (`"fit": "contain"` for whole planets).
- `"backend": "stock"` (Pixabay or Pexels video, free licence) for comedy cutaways and desi comparisons: traffic jam, people
  laughing, chai, crowded train, wedding dance, sweating man, office, cricket, explosion. Give a concrete English
  `query` ("mumbai traffic jam", "man sweating heat"). At least 3 stock scenes per reel, at least 3 NASA scenes.
- Never use movie clips, Bollywood scenes, celebrity footage, memes made by others or any non-free footage.
Fast camera moves (zoom_in on the hook).

## 4. Validate
`build_video.py --script scripts/episode_{N}.json --validate-only`. Fix every error and every warning you reasonably can,
especially hook warnings.

## 4b. Pictures
`preview_visuals.py --script scripts/episode_{N}.json`, open `build/preview/ep_{N:03d}_visuals.jpg` with the Read tool,
make sure column [0] of each row matches the narration. Pin better ones with `"nasa_id"` or rewrite the query. No
podium photos, logos, charts, people in offices or off-topic shots. The hook picture must be dramatic.

## 5. Record it
Append the reel to `series_history.json` (`status: "scripted"`, `output_file: null`, plus `angle`).

## 6. Render (local runs only; the 4 AM cloud task skips this, GitHub renders)
`build_video.py --script scripts/episode_{N}.json`. If runtime warnings say under 25 s or over 40 s, or the hook runs
over 2.5 s, fix the narration and re-render with `--force`.

## 7. Report
Output file, runtime, topic type, and the hook line.
