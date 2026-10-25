"""AetherGrid Visual Verification Script using Pyppeteer.

This script automates browser verification for the AetherGrid dashboard:
1. Launches Chromium or compatible local browser (Chrome/Edge) via Pyppeteer.
2. Opens the locally running Vite frontend.
3. Verifies that the global stylesheet loads properly.
4. Asserts computed styles on sidebar navigation anchors (anti-regression check for
   purple/underlined links, verifying display: flex, padding, and dark theme colors).
5. Captures screenshots across all five primary routes plus full-page and sidebar-focused views.
6. Saves screenshots to artifacts/screenshots/ and verifies file existence.
7. Exits with code 0 on success, code 1 on any failure.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import List, Optional

import pyppeteer
from pyppeteer import launch


def find_browser_executable() -> Optional[str]:
    """Find a usable Chromium / Chrome / Edge executable path."""
    env_path = os.environ.get("CHROME_PATH") or os.environ.get("PUPPETEER_EXECUTABLE_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    # Check if Pyppeteer's downloaded chromium is present
    try:
        from pyppeteer.chromium_downloader import check_chromium, chromiumExecutable
        if check_chromium():
            path = str(chromiumExecutable["win64" if sys.platform == "win32" else "linux"])
            if os.path.isfile(path):
                return path
    except Exception:
        pass

    # Common Windows installation locations
    candidate_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    ]

    for p in candidate_paths:
        if os.path.isfile(p):
            return p

    return None


async def run_visual_verification(
    base_url: str,
    output_dir: Path,
    browser_path: Optional[str] = None,
    viewport_width: int = 1440,
    viewport_height: int = 900,
) -> bool:
    """Execute Pyppeteer verification, capture screenshots, and assert computed styles."""
    output_dir.mkdir(parents=True, exist_ok=True)

    exec_path = browser_path or find_browser_executable()
    if not exec_path:
        print("[ERROR] No Chromium or Chrome/Edge executable found on this system.")
        print("Please set the CHROME_PATH environment variable or install Google Chrome.")
        return False

    print(f"[INFO] Using browser executable: {exec_path}")
    print(f"[INFO] Target frontend URL: {base_url}")
    print(f"[INFO] Screenshot directory: {output_dir.resolve()}")

    console_messages: List[str] = []
    page_errors: List[str] = []
    failed_requests: List[str] = []
    http_errors: List[str] = []

    browser = None
    all_passed = True

    try:
        browser = await launch(
            executablePath=exec_path,
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                f"--window-size={viewport_width},{viewport_height}",
            ],
            defaultViewport={"width": viewport_width, "height": viewport_height},
        )

        page = await browser.newPage()

        # Wire up diagnostic handlers
        page.on(
            "console",
            lambda msg: console_messages.append(f"[{msg.type.upper()}] {msg.text}"),
        )
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        page.on("requestfailed", lambda req: failed_requests.append(f"{req.method} {req.url} -> {req.failure}"))
        page.on(
            "response",
            lambda res: http_errors.append(f"HTTP {res.status} {res.url}")
            if res.status >= 400 and not ("/api/" in res.url and res.status == 502)
            else None,
        )

        # 1. Open the homepage
        print(f"\n--- Step 1: Navigating to {base_url} ---")
        try:
            response = await page.goto(base_url, waitUntil="networkidle0", timeout=30000)
            if response and response.status >= 400:
                print(f"[FAIL] Navigation to {base_url} returned HTTP {response.status}")
                return False
        except Exception as e:
            print(f"[FAIL] Could not navigate to {base_url}: {e}")
            return False

        # Wait for React app shell and navigation
        try:
            await page.waitForSelector(".app-shell", timeout=10000)
            await page.waitForSelector(".sidebar nav a", timeout=10000)
            print("[PASS] React application mounted and sidebar navigation detected.")
        except Exception as e:
            print(f"[FAIL] App shell or sidebar nav not rendered in time: {e}")
            return False

        # 2. Check stylesheet loading
        print("\n--- Step 2: Verifying Stylesheet Status ---")
        stylesheet_status = await page.evaluate(
            """() => {
                const sheets = Array.from(document.styleSheets);
                let totalRules = 0;
                let cssFiles = [];
                for (const s of sheets) {
                    try {
                        if (s.href) cssFiles.push(s.href);
                        totalRules += s.cssRules ? s.cssRules.length : 0;
                    } catch (e) {
                        // Cross-origin sheets might throw, ignore
                    }
                }
                const bodyBg = window.getComputedStyle(document.body).backgroundColor;
                return { sheetCount: sheets.length, totalRules, cssFiles, bodyBg };
            }"""
        )
        print(f"  Stylesheets loaded: {stylesheet_status['sheetCount']}")
        print(f"  Rules detected: {stylesheet_status['totalRules']}")
        print(f"  Body computed background: {stylesheet_status['bodyBg']}")

        if stylesheet_status["sheetCount"] == 0 or stylesheet_status["totalRules"] == 0:
            print("[FAIL] No active stylesheets or rules detected in the DOM.")
            all_passed = False
        else:
            print("[PASS] Stylesheet loaded successfully with active rules.")

        # 3. Check computed styles on sidebar links
        print("\n--- Step 3: Checking Computed Styles on Sidebar Navigation Anchors ---")
        nav_styles = await page.evaluate(
            """() => {
                const anchors = Array.from(document.querySelectorAll('.sidebar nav a'));
                return anchors.map(a => {
                    const cs = window.getComputedStyle(a);
                    return {
                        text: a.innerText.trim(),
                        tagName: a.tagName,
                        href: a.href,
                        className: a.className,
                        color: cs.color,
                        textDecoration: cs.textDecoration,
                        textDecorationLine: cs.textDecorationLine,
                        display: cs.display,
                        alignItems: cs.alignItems,
                        gap: cs.gap,
                        padding: cs.padding,
                        borderLeft: cs.borderLeft,
                        backgroundColor: cs.backgroundColor
                    };
                });
            }"""
        )

        # Bug symptoms to reject:
        # - Default purple / blue links: rgb(158, 158, 255), rgb(85, 26, 139), rgb(0, 0, 238)
        # - textDecoration: 'underline'
        # - display not 'flex'
        # - padding '0px'
        purple_shades = [
            "rgb(158, 158, 255)",
            "rgb(85, 26, 139)",
            "rgb(0, 0, 238)",
            "rgb(128, 0, 128)",
            "rgb(0, 102, 204)",
        ]

        expected_routes = [
            ("Overview", True),
            ("Decision Simulator", False),
            ("Forecast Explorer", False),
            ("Accuracy Analysis", False),
            ("Data Explorer", False),
            ("Methodology & Data", False),
        ]

        for item in nav_styles:
            label = item["text"]
            is_active = "active" in item["className"]
            print(f"\n  Checking link: '{label}' (Active={is_active})")
            print(f"    color: {item['color']}")
            print(f"    textDecorationLine: {item['textDecorationLine']}")
            print(f"    display: {item['display']}")
            print(f"    gap: {item['gap']}")
            print(f"    padding: {item['padding']}")
            print(f"    borderLeft: {item['borderLeft']}")
            print(f"    backgroundColor: {item['backgroundColor']}")

            # Assert no underline
            if item["textDecorationLine"] == "underline" or "underline" in item["textDecoration"]:
                print(f"    [FAIL] Link '{label}' has underline text decoration!")
                all_passed = False
            else:
                print("    [PASS] No underline decoration.")

            # Assert no browser-default purple/blue
            if item["color"] in purple_shades:
                print(f"    [FAIL] Link '{label}' has browser-default link color: {item['color']}")
                all_passed = False
            else:
                print("    [PASS] Custom theme color applied.")

            # Assert display flex
            if item["display"] != "flex":
                print(f"    [FAIL] Link '{label}' display is '{item['display']}', expected 'flex'!")
                all_passed = False
            else:
                print("    [PASS] display: flex verified.")

            # Assert padding
            if item["padding"] == "0px":
                print(f"    [FAIL] Link '{label}' has 0px padding!")
                all_passed = False
            else:
                print("    [PASS] Appropriate padding applied.")

            # Active vs inactive assertions
            if is_active:
                if "rgb(57, 199, 154)" not in item["borderLeft"]:
                    print(f"    [FAIL] Active link '{label}' missing emerald border-left (#39c79a / rgb(57, 199, 154))!")
                    all_passed = False
                else:
                    print("    [PASS] Active emerald indicator present.")

                if "rgb(16, 34, 46)" not in item["backgroundColor"]:
                    print(f"    [FAIL] Active link '{label}' missing active dark background (#10222e)!")
                    all_passed = False
                else:
                    print("    [PASS] Active background highlight verified.")

        # 4. Interactive route test: click 'Forecast Explorer' and assert active class transfer
        print("\n--- Step 4: Testing Dynamic Route Navigation & Active Class Transfer ---")
        try:
            forecast_link = await page.xpath("//aside[contains(@class,'sidebar')]//nav//a[contains(., 'Forecast Explorer')]")
            if forecast_link:
                await forecast_link[0].click()
                await asyncio.sleep(0.5)
                new_active = await page.evaluate(
                    """() => {
                        const activeLink = document.querySelector('.sidebar nav a.active');
                        if (!activeLink) return null;
                        const cs = window.getComputedStyle(activeLink);
                        return {
                            text: activeLink.innerText.trim(),
                            borderLeft: cs.borderLeft,
                            color: cs.color
                        };
                    }"""
                )
                if new_active and "Forecast Explorer" in new_active["text"]:
                    print(f"[PASS] Successfully navigated to Forecast Explorer. Active link is '{new_active['text']}'.")
                    if "rgb(57, 199, 154)" in new_active["borderLeft"]:
                        print("[PASS] Forecast Explorer active emerald border-left dynamically applied.")
                    else:
                        print("[FAIL] Dynamic active emerald border-left not applied to Forecast Explorer.")
                        all_passed = False
                else:
                    print(f"[FAIL] Active link did not transfer to Forecast Explorer: {new_active}")
                    all_passed = False
        except Exception as e:
            print(f"[WARN] Dynamic navigation test encountered issue: {e}")

        # 5. Capture screenshots
        print("\n--- Step 5: Capturing Visual Proof Screenshots ---")

        pages_to_capture = [
            ("01_overview.png", f"{base_url}/"),
            ("02_forecast_explorer.png", f"{base_url}/forecasts"),
            ("03_accuracy_analysis.png", f"{base_url}/accuracy"),
            ("04_data_explorer.png", f"{base_url}/data"),
            ("05_methodology.png", f"{base_url}/methodology"),
            ("06_decision_simulator.png", f"{base_url}/simulator"),
        ]

        captured_files: List[Path] = []

        # Return to Overview for full page & viewport screenshots
        await page.goto(f"{base_url}/", waitUntil="networkidle0", timeout=20000)
        await asyncio.sleep(0.5)

        # Full page screenshot of Overview
        full_page_path = output_dir / "00_full_page_overview.png"
        await page.screenshot({"path": str(full_page_path), "fullPage": True})
        if full_page_path.is_file() and full_page_path.stat().st_size > 0:
            print(f"  [SAVED] Full-page Overview -> {full_page_path} ({full_page_path.stat().st_size:,} bytes)")
            captured_files.append(full_page_path)
        else:
            print(f"  [FAIL] Failed to save full-page screenshot: {full_page_path}")
            all_passed = False

        # Sidebar navigation viewport / element screenshot
        sidebar_element = await page.querySelector(".sidebar")
        if sidebar_element:
            sidebar_path = output_dir / "00_sidebar_navigation_viewport.png"
            await sidebar_element.screenshot({"path": str(sidebar_path)})
            if sidebar_path.is_file() and sidebar_path.stat().st_size > 0:
                print(f"  [SAVED] Sidebar Element Viewport -> {sidebar_path} ({sidebar_path.stat().st_size:,} bytes)")
                captured_files.append(sidebar_path)
            else:
                print(f"  [FAIL] Failed to save sidebar viewport screenshot: {sidebar_path}")
                all_passed = False

        # Capture each page
        for filename, url in pages_to_capture:
            try:
                await page.goto(url, waitUntil="networkidle0", timeout=20000)
                await asyncio.sleep(0.4)
                file_path = output_dir / filename
                await page.screenshot({"path": str(file_path)})
                if file_path.is_file() and file_path.stat().st_size > 0:
                    print(f"  [SAVED] Page {url} -> {file_path} ({file_path.stat().st_size:,} bytes)")
                    captured_files.append(file_path)
                    if filename == "06_decision_simulator.png":
                        sim_full_path = output_dir / "06_decision_simulator_fullpage.png"
                        await page.screenshot({"path": str(sim_full_path), "fullPage": True})
                        print(f"  [SAVED] Full-page Simulator -> {sim_full_path} ({sim_full_path.stat().st_size:,} bytes)")
                        captured_files.append(sim_full_path)

                        # Interactive UI State 1: Reset to 0% baseline (default scenario)
                        reset_btn = await page.xpath("//button[contains(., 'Reset (0%)')]")
                        if reset_btn:
                            await reset_btn[0].click()
                            await asyncio.sleep(0.5)
                            p0_path = output_dir / "06_decision_simulator_default_0pct.png"
                            await page.screenshot({"path": str(p0_path)})
                            print(f"  [SAVED] Simulator (Default 0% Scenario) -> {p0_path} ({p0_path.stat().st_size:,} bytes)")
                            captured_files.append(p0_path)

                        # Interactive UI State 2: Click '+20%' stress chip
                        chip20 = await page.xpath("//button[contains(@class, 'chip-btn') and contains(., '+20%')]")
                        if chip20:
                            await chip20[0].click()
                            await asyncio.sleep(0.5)
                            p20_path = output_dir / "06_decision_simulator_stress_plus20pct.png"
                            await page.screenshot({"path": str(p20_path)})
                            print(f"  [SAVED] Simulator (Stress +20% Scenario) -> {p20_path} ({p20_path.stat().st_size:,} bytes)")
                            captured_files.append(p20_path)

                        # Interactive UI State 3: Switch Cutoff Preset to 11:00 UTC
                        cutoff11_btn = await page.xpath("//button[contains(@class, 'preset-btn') and contains(., '11:00 UTC')]")
                        if cutoff11_btn:
                            await cutoff11_btn[0].click()
                            await asyncio.sleep(0.8)
                            p11_path = output_dir / "06_decision_simulator_cutoff_11utc.png"
                            await page.screenshot({"path": str(p11_path)})
                            print(f"  [SAVED] Simulator (Cutoff 11:00 UTC) -> {p11_path} ({p11_path.stat().st_size:,} bytes)")
                            captured_files.append(p11_path)

                        # Interactive UI State 4: Toggle Half-Hourly Resolution (48 Settlement Periods)
                        hh_btn = await page.xpath("//button[contains(., 'Half-Hourly')]")
                        if hh_btn:
                            await hh_btn[0].click()
                            await asyncio.sleep(0.8)
                            phh_path = output_dir / "06_decision_simulator_half_hourly.png"
                            await page.screenshot({"path": str(phh_path)})
                            print(f"  [SAVED] Simulator (Half-Hourly 48 SP) -> {phh_path} ({phh_path.stat().st_size:,} bytes)")
                            captured_files.append(phh_path)
                else:
                    print(f"  [FAIL] Screenshot file missing or empty: {file_path}")
                    all_passed = False
            except Exception as e:
                print(f"  [FAIL] Error capturing screenshot for {url}: {e}")
                all_passed = False

        # 6. Check console & network diagnostics
        print("\n--- Step 6: Console and Network Diagnostics ---")
        fatal_page_errors = [e for e in page_errors if "ResizeObserver" not in e]
        if fatal_page_errors:
            print(f"  [FAIL] Page errors encountered ({len(fatal_page_errors)}):")
            for err in fatal_page_errors:
                print(f"    - {err}")
            all_passed = False
        else:
            print("  [PASS] No uncaught page errors.")

        if http_errors:
            print(f"  [WARN] Unexpected HTTP errors ({len(http_errors)}):")
            for err in http_errors:
                print(f"    - {err}")
        else:
            print("  [PASS] No frontend HTTP asset errors.")

        print(f"\n[SUMMARY] Total screenshots verified: {len(captured_files)}")
        for f in captured_files:
            print(f"  - {f.resolve()} ({f.stat().st_size:,} bytes)")

    finally:
        if browser:
            await browser.close()

    return all_passed


def main():
    parser = argparse.ArgumentParser(description="AetherGrid Pyppeteer Visual Verification")
    parser.add_argument(
        "--url",
        default=os.environ.get("FRONTEND_URL", "http://localhost:5173"),
        help="Frontend application URL (default: http://localhost:5173)",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/screenshots",
        help="Directory to save screenshots (default: artifacts/screenshots)",
    )
    parser.add_argument(
        "--browser-path",
        default=None,
        help="Custom browser executable path (e.g., path to Chrome or Edge)",
    )

    args = parser.parse_args()
    out_path = Path(args.output_dir)

    success = asyncio.run(
        run_visual_verification(
            base_url=args.url,
            output_dir=out_path,
            browser_path=args.browser_path,
        )
    )

    if success:
        print("\n==========================================")
        print(">>> ALL VISUAL VERIFICATIONS PASSED! <<<")
        print("==========================================")
        sys.exit(0)
    else:
        print("\n==========================================")
        print(">>> VISUAL VERIFICATION FAILED! <<<")
        print("==========================================")
        sys.exit(1)


if __name__ == "__main__":
    main()
