# FootStat: two-minute demo script

**Before you start (about 5 minutes ahead):** start the backend and frontend as described in the README under "Running the app". Open http://127.0.0.1:8000/api/health and confirm `"status": "ok"`. Then open http://localhost:5173 in a browser window at least 1,280 px wide, so the side panels sit next to the pitch.

All numbers below are what the app shows for the current dataset and model. If you retrain on different data, read the numbers off the screen instead.

---

## 1. Dashboard (about 30 seconds)

*Open **Dashboard**.*

> "FootStat estimates expected goals, the probability that a shot becomes a goal. The data is real StatsBomb event data from all 64 matches of the 2022 World Cup.
>
> There were **1,453 shots** and **169 goals**, about 11.6% of shots, so **1,284** didn't score. Our model's predicted xG over all those shots adds up to **170.8**, close to the 169 goals actually scored. StatsBomb's own model gives 155.9.
>
> The chart compares goals (bars) with predicted xG (line) for each match day. The leaderboard ranks players by total xG: **Messi leads with 4.78 xG** from 32 shots, and he scored 7, ahead of Mbappé with 4.03."

## 2. Shot Map (about 30 seconds)

*Open **Shot Map**.*

> "Every dot is a real shot at its recorded position. We're attacking the goal at the top. Green dots are goals, red dots aren't, and bigger dots mean higher xG. Most of the big green dots sit in the six-yard box and the middle of the penalty area."

*Type **mbappe** in Player (accents and capitals don't matter) and choose **Goals**. Eight green dots remain. Near the bottom-left of the penalty area, just inside its edge, two small dots sit side by side. Click the **right-hand one**. The panel should read **Argentina vs France, 2022-12-18**, Location 104.8, 30.1. (The left-hand dot is his goal against Poland.)*

> "This is Mbappé's goal in the final against Argentina. From the edge of the box our model gave it **0.105 xG**, about a 1-in-10 chance, and StatsBomb's benchmark says 0.102, so the two models agree. Great finishers score shots like this more often than xG expects."

*(Tip: dense areas overlap, so filter by player or team before clicking a specific shot.)*

## 3. Shot Predictor (about 30 seconds)

*Open **Shot Predictor**. Click just in front of the goal, on the line of the six-yard box. Body part: **Right Foot**. Click **Predict**.*

> "Now a hypothetical shot. I pick a spot, and the frontend sends the coordinates and body part to the FastAPI backend, which runs the saved scikit-learn pipeline. The browser doesn't calculate anything itself. Close and central with the right foot, the model gives better than even odds."

*Read the percentage off the screen: about **56%** on the six-yard line (x 114, y 40), rising to about **72%** halfway into the six-yard box. Change Body part to **Head** and click **Predict** again.*

> "The same spot as a header roughly halves the chance (about **22–36%** here), because headers are much harder to convert. Move out to around 25 yards and it falls to about 5%."

*(Exact values depend on where you click. The panel also shows the distance and angle the model used.)*

## 4. Evaluation and limitations (about 30 seconds)

*Go back to **Dashboard** and scroll to the **Model** card.*

> "We evaluated the model honestly. Whole matches were held out (16 matches, 378 shots) so it never saw them during training. On those, log loss is **0.278** against **0.349** for just guessing the average rate, and ROC-AUC is **0.81**: given a random goal and a random miss, the model ranks the goal higher about 81% of the time.
>
> It's a simple logistic regression on location and body part, so it's weaker than StatsBomb's professional model, which scores 0.238 and 0.86.
>
> Limitations: it doesn't know shot type, so **penalties come out at about 26%** when they really go in about three times out of four. It has no defender or goalkeeper positions. And it's one tournament with only 42 goals in the test set, so the numbers are indicative, not precise."

---

### If something goes wrong

- **Red "Can't reach the FootStat API" banner:** the backend isn't running. Start it in Window 1, then click **Retry**.
- **`/api/health` returns 503:** the error message names the missing file. Re-run the preprocessing or training steps in the README.
- **"running scripts is disabled" in PowerShell:** you used `npm` or `Activate.ps1`. Use `npm.cmd` and `.\backend\.venv\Scripts\python.exe` as written in the README.
