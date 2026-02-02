# Whisk Agent Documentation

The `WhiskAgent` is a browser-automation based image generation service that interacts with [Google Whisk](https://labs.google/fx/tools/whisk). It allows the application to generate high-quality AI images without a direct API, leveraging Google's advanced models.

## 🏗️ Architecture & Workflow

The agent uses **Playwright** to automate a Chrome browser instance. It maintains a persistent user profile to stay logged in and bypasses typical automation detection.

### Core Components
- **Browser Context:** Managed via `get_context()`, using a persistent profile stored in `~/.whisk-profile`.
- **Single Generation:** `generate_image()` handles the full lifecycle of a single prompt (Login check -> Aspect Ratio -> [Character Upload] -> Prompt -> Generate -> Download).
- **Batch Generation:** `generate_batch()` optimizes generation by reusing a single browser page for multiple prompts, only uploading character references once at the start.

---

## 🔐 Authentication

Whisk requires a Google Account.
1. **Manual Setup:** On the first run, the browser will open in headful mode (visible). The user must manually sign in to their Google account.
2. **Persistent Profile:** Once signed in, the session is saved in `PROFILE_PATH`. Subsequent runs will use this profile to stay authenticated.
3. **Helper Script:** If authentication fails, users should run `python scripts/auth_whisk.py` (if available) or any test script that launches the browser headfully to re-verify the session.

---

## 🎨 Image Generation Logic

### 1. Aspect Ratio
The agent supports **Landscape (16:9)** and **Portrait (9:16)**.
- It finds the `aspect_ratio` icon button.
- Selects the target ratio from the dropdown.
- Clicks away from the menu to confirm.

### 2. Prompting
- The prompt is entered into the main `textarea` (placeholder: "Describe your idea").
- A `style_suffix` can be appended to every prompt to maintain a consistent look (e.g., "high-quality Disney/Pixar 3D animation style").

### 3. Submission
The agent searches for the "Generate" button using multiple strategies:
- **Strategy A:** Targeted icon search (`arrow_forward`).
- **Strategy B:** ARIA-label fallback ("Submit prompt", "Generate").
- **Strategy C:** Last available icon-button in the main container.

---

## 👤 Character Consistency (Subject Uploads)

One of Whisk's key features is the "Add Image" sidebar, which allows for **Subject References**.

### The Upload Process:
1. **Sidebar Activation:** Clicks "ADD IMAGES" to reveal the side panel.
2. **Subject Identification:** Locates the "Subject" category (as opposed to Scene or Style).
3. **Slot Management:**
   - If more characters are provided than slots exist, it clicks the `control_point` (plus icon) near the Subject header to add a new category.
4. **Image Upload:**
   - Mentions two primary upload strategies:
     - **Direct Input:** Finds the hidden `<input type="file">` inside the slot container.
     - **Hover-Reveal:** Hovers over the slot (at 85% depth) to reveal the "Upload Image" button, then triggers the file chooser.
5. **Analysis Wait:** After uploading, the agent waits **12 seconds** for Google's servers to analyze the features of the uploaded characters before proceeding to generate.

---

## 📥 Downloading

To ensure maximum quality, the agent prefers the dedicated download button over a simple "Save Image As":
1. **Hover Reveal:** Hovers over the generated image in the gallery.
2. **Download Trigger:** Clicks the button containing the `download` icon.
3. **Playwright `expect_download`:** Captures the resulting file stream directly from the browser.

---

## 🛠️ Maintenance & Enhancements

### Current Working Version ("The Stable Revert")
The current version has been reverted to a known-stable state that prioritizes:
- **Global Input Management:** Simpler slot identification that avoids complex DOM tree traversing.
- **Robust Hover logic:** Specifically tailored to the current Google Whisk UI layout.

### Future Enhancements
- **Style References:** Adding support for the "Style" category in the sidebar (currently removed for stability).
- **Parallel Generations:** Implementing multiple page contexts if higher throughput is required.
- **Improved Spinner Detection:** Replacing fixed sleep times (`asyncio.sleep`) with smarter detection of the "Generation Finished" UI state.

---

## 🔌 API & Backend Integration (`main.py`)

The Whisk Agent is exposed via the FastAPI backend to allow the frontend to trigger generations.

### 1. Endpoint: `/scenes/generate-batch`
This is the primary endpoint for bulk image generation.
- **Request Model:** `GenerateBatchRequest` (contains prompts, niche ID, style suffix, and character image objects).
- **Agent Initialization:** The agent is initialized with `headless=False` (displayed) to ensure maximum stability and allow for manual intervention if Google flags the session.

### 2. Character Reference Handling
Since Whisk requires local file paths for uploads, `main.py` performs the following pre-processing:
1. **Source:** Receives a list of `character_images` (URLs from cloud storage).
2. **Download:** Uses `httpx` to download these images to the server.
3. **Temporary Files:** Saves images into `tempfile.NamedTemporaryFile` with a `.png` suffix.
4. **Local Paths:** Passes the `pathlib.Path` objects of these temp files to the `WhiskAgent.generate_batch` method.

### 3. Result Processing & Cloud Storage
Once the agent returns the list of image bytes:
1. **Looping:** The API iterates through the results.
2. **Cloud Upload:** Uses `R2Storage` to upload the raw bytes to a path like `scenes/{niche_id}/batch_{uuid}_scene_{i}.png`.
3. **URL Generation:** Returns the public Cloudflare R2 URLs back to the frontend to update the UI.

## 📋 Data Flow Summary
`Frontend (Prompts + URLs)` -> `API (main.py)` -> `Temp Storage (Local .png)` -> `WhiskAgent (Playwright/Chrome)` -> `Whisk UI` -> `Download Byte Stream` -> `R2 Storage` -> `Final URL to Frontend`

---

## 🧪 Testing & Verification

Several scripts are available in the `scripts/` directory to verify the agent's functionality and manage authentication.

### 1. Batch Generation Test (`scripts/test_whisk_batch.py`)
This is the primary unit test for the agent's bulk generation capabilities.
- **Purpose:** Verifies that the agent can open a browser, navigate to Whisk, and generate multiple images in a single session by reusing a tab.
- **How to run:**
  ```powershell
  python scripts/test_whisk_batch.py
  ```
- **What it tests:**
  - Browser instantiation and persistent profile loading.
  - Navigation to the project page.
  - Sequence of prompt entry, generation, and simulated download wait.

### 2. Authentication Helper (`scripts/auth_whisk.py`)
Used to manually establish the Google session.
- **Purpose:** Opens the browser in headful mode and navigates to the login page.
- **Action:** The user manually signs in once. The session is saved to `~/.whisk-profile`.
- **How to run:**
  ```powershell
  python scripts/auth_whisk.py
  ```

### 3. Diagnostic Tools
- **`diag_whisk_screenshot.py`:** Captures a full-page screenshot of the current Whisk state. Essential for debugging UI changes or "Selector not found" errors.
- **`test_whisk_hover.py`:** Specifically tests the complex hover-and-click logic required for revealed upload buttons in the character sidebar.

---

> [!NOTE]
> All browser interactions include a `disable-blink-features=AutomationControlled` flag to reduce the risk of the account being flagged as a bot.
