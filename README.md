# 🎨 AI Design Auditor

A Python tool that uses multimodal AI (Gemini Pro) to audit application UIs against their original Figma designs.

Instead of brittle, 1-to-1 pixel matching, this tool intelligently identifies and matches components (like buttons, text, and images) from both screenshots. It then runs "flexible" tests on these matched pairs to check for layout, style, and padding discrepancies, generating an interactive dashboard to visualize the results.


---

## ✨ Key Features

* **🤖 AI-Powered Component Matching:** No more brittle `name` or `ID` matching. The AI (Google Gemini 2.5 Pro) visually identifies and pairs corresponding elements from the Figma and App images.
* **Flexible Layout Validation:** Checks for *real* developer issues, not just pixel-perfect alignment.
    * **Dimensions:** Verifies if `width` and `height` are proportionally correct.
    * **Relational Spacing:** Verifies vertical `margin-top` (spacing between elements).
    * **Padding:** Verifies horizontal `padding-left` and `padding-right` relative to the screen edges.
* **Deep Style Auditing:** The AI *estimates* and compares critical style properties:
    * `fontSize` (e.g., 28dp vs 26.5dp)
    * `color` (e.g., #FFFFFF vs #FEFEFE)
    * `backgroundColor` (e.g., #2C2C2C vs #2A2A2A)
* **🖱️ Interactive HTML Dashboard:** Generates a "cool" report that:
    * Shows a visual side-by-side of the images being compared.
    * Lists all matched components with `✅ Pass` / `❌ Fail` / `🎨 Audit` icons.
    * **Highlights component bounding boxes** on the images when you click a row.
    * Provides a "click-to-expand" detail panel for every component, showing test results and raw AI data.
* **📜 Multi-Part "Scroll" Support:** Analyzes long, scrolling pages by stitching together multiple "parts" (e.g., `part1.png`, `part2.png`).
* **⚡ Hybrid Mode:** Can run in two modes:
    1.  **Automatic (ADB):** Automatically takes screenshots and handles scrolling for you.
    2.  **Manual (File-Based):** You provide all the App screenshots manually for 100% reliable, deterministic tests.

---

## ⚙️ How It Works

This tool's "secret" is that it delegates the *brittle* task of "matching" to the AI, and only uses Python for the *flexible* task of "testing."

1.  **Input:** The user provides `N` Figma parts (e.g., `figma_1.png`) and either provides `N` App parts manually (`--app-parts`) or lets the tool take them via ADB.
2.  **Cropping:** The script applies the user's `crop` settings (e.g., `--app-crop-top 80`) to remove system UI like status bars and navigation bars. This *dramatically* improves AI accuracy.
3.  **AI Matching (The Core):** For each `figma_part_N.png` and `app_part_N.png` pair, the `image_analyzer.py` script sends *both images at the same time* to the Gemini 1.5 Pro model.
4.  **AI Prompt (The "Brain"):** The prompt (V6) explicitly instructs the AI:
    > "You are a UI/UX expert. Find the corresponding (matched) components from these two images based on geometry and type. Return a SINGLE JSON list of these pairs. If a component has no match, DO NOT include it."
5.  **AI Output:** The AI returns *one* JSON list of *pre-matched pairs*, like so:
    ```json
    [
      {
        "name": "driver_name",
        "figma_analysis": { "bounds": {...}, "estimated_color": "#FFFFFF" },
        "app_analysis": { "bounds": {...}, "estimated_color": "#FEFEFE" }
      }
    ]
    ```
6.  **Python Validation (`comparator.py`):** This script (the "Tester") is now very simple. It **trusts the AI's matches** and just iterates through the list. For each pair, it runs its "flexible" tests (padding, margin, etc.) using the `DEFAULT_TOLERANCE_PX` defined in `config.py`.
7.  **Report Generation (`report_generator.py`):** Creates the final `report.html` dashboard, embedding the test results and raw `bounds` data into the HTML, ready for the JavaScript highlighting functions.

---

## 🚀 Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/ai-design-auditor.git
    cd ai-design-auditor
    ```

2.  **Create a virtual environment (Recommended):**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install google-generativeai pillow python-dotenv fastapi uvicorn python-multipart
    ```

4.  **(Optional) Ensure ADB is installed:** If you want to use "Automatic Mode," make sure `adb` is installed and accessible in your system's PATH.

---

## 🔑 Configuration

This tool requires a Google Gemini API key.

1.  Get your free API key from **Google AI Studio**.
2.  In the project's root folder, create a file named `.env`
3.  Add your key to this file:

    ```
    GOOGLE_API_KEY="YOUR_API_KEY_HERE"
    ```

4.  (Optional) Open `config.py` to adjust the `DEFAULT_TOLERANCE_PX` (default is `3`). This is the number of pixels a component can be "off" before it's flagged as an error.

---

## 🖥️ Web GUI Usage (Recommended)

The easiest way to use the tool is via the modern Web Interface.

1.  **Start the Server:**
    ```bash
    uvicorn server:app --host 0.0.0.0 --port 8000 --reload
    ```

2.  **Open in Browser:**
    Go to `http://localhost:8000`

3.  **Features:**
    *   **Drag & Drop Upload:** Easily upload Figma designs and App screenshots.
    *   **Visual Previews:** See your uploaded images before analyzing.
    *   **Side-by-Side Comparison:** View the Figma design and App implementation next to each other.
    *   **Interactive Highlighting:** Click on any component in the results table to see it highlighted on both images.
    *   **AI Analysis Mode:** Choose between XML-based (UIAutomator) or AI-based (Visual) analysis for the App screenshot.

## 🛠️ CLI Usage

You can also run the tool from the command line:

### Mode 1: Automatic (ADB)
Best for simple, single-screen (non-scrolling) tests.

1.  Open the correct screen on your connected Android device/emulator.
2.  Run the script, pointing to your single Figma screenshot.
3.  **Crucially, provide the `crop` values** to remove the system Status Bar and Navigation Bar from the *App's* screenshot.

**Command:**
```bash
python run_audit.py \
    --figma-parts figma_login.png \
    --app-crop-top 80 \
    --app-crop-bottom 140
```