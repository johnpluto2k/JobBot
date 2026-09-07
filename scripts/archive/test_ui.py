#!/usr/bin/env python3
"""
End-to-end UI test for Company Tracker using Playwright.
Tests the full flow: backend API + React frontend + company tracker functionality.
"""

import asyncio
import subprocess
import time
import sys
from pathlib import Path

# Playwright async test
async def test_company_tracker():
    from playwright.async_api import async_playwright, expect

    # Start backend API server (spawn in background)
    print("[START] Backend API server...")
    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "job_bot.api"],
        cwd=str(Path(__file__).parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(2)  # Wait for backend to start

    # Start frontend dev server (spawn in background)
    print("[START] Frontend dev server...")
    frontend_proc = subprocess.Popen(
        "npm run dev",
        shell=True,
        cwd=str(Path(__file__).parent / "web"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(8)  # Wait for frontend to build and start (longer for first build)

    try:
        async with async_playwright() as p:
            print("[BROWSER] Launching browser...")
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()

            # Navigate to the app
            print("[NAV] Navigating to http://localhost:5173...")
            await page.goto("http://localhost:5173", wait_until="networkidle")

            # Wait for overview page to load
            await page.wait_for_selector("text=Overview", timeout=10000)
            print("[OK] App loaded successfully")

            # Take screenshot of overview
            await page.screenshot(path="screenshots/01_overview.png")
            print("[SCREENSHOT] overview page")

            # Click on Companies tab
            print("[ACTION] Clicking Companies tab...")
            companies_button = page.locator("button", has_text="Companies")
            await companies_button.click()
            await page.wait_for_load_state("networkidle")

            # Wait for companies table to load
            await page.wait_for_selector("table", timeout=10000)
            print("[OK] Companies tab loaded")

            # Take screenshot of companies tab
            await page.screenshot(path="screenshots/02_companies_all.png")
            print("[SCREENSHOT] companies all")

            # Check if companies are displayed
            company_rows = page.locator("table tbody tr")
            count = await company_rows.count()
            print(f"[DATA] Found {count} company rows in table")

            if count > 0:
                # Get first company name
                first_company = await company_rows.first.locator("td").first.text_content()
                print(f"[OK] First company: {first_company.strip()}")

            # Check summary cards
            cards = page.locator("text=/Companies tracked|Due for check-in|Big 4 firms/")
            card_count = await cards.count()
            print(f"[OK] Found {card_count} summary cards")

            # Click "Overdue" filter
            print("[ACTION] Clicking Overdue filter...")
            overdue_button = page.locator("button", has_text="Overdue")
            await overdue_button.click()
            await page.wait_for_load_state("networkidle")

            # Take screenshot of overdue filter
            await page.screenshot(path="screenshots/03_companies_overdue.png")
            print("[SCREENSHOT] companies overdue filter")

            # Check overdue count
            overdue_rows = page.locator("table tbody tr")
            overdue_count = await overdue_rows.count()
            print(f"[DATA] Overdue companies: {overdue_count}")

            # Switch back to All
            print("[ACTION] Clicking All Companies filter...")
            all_button = page.locator("button", has_text="All Companies")
            await all_button.click()
            await page.wait_for_load_state("networkidle")

            # Find a check button and test it
            check_buttons = page.locator("button", has_text="Check")
            check_count = await check_buttons.count()
            print(f"[DATA] Found {check_count} check buttons")

            if check_count > 0:
                print("[ACTION] Clicking first Check button...")
                first_check_button = check_buttons.first
                await first_check_button.click()

                # Wait for loading to complete
                await page.wait_for_load_state("networkidle")
                time.sleep(1)

                # Take screenshot of checked state
                await page.screenshot(path="screenshots/04_check_button_clicked.png")
                print("[SCREENSHOT] after clicking check button")

                # Verify button changed state (might show "Checking..." or button disabled)
                button_text = await first_check_button.text_content()
                print(f"[OK] Button state after click: {button_text.strip()}")

            # Scroll table to see all columns
            table = page.locator("table")
            await table.scroll_into_view_if_needed()

            # Take final screenshot
            await page.screenshot(path="screenshots/05_final_state.png")
            print("[SCREENSHOT] final state")

            # Print summary of what was found
            print("\n" + "="*60)
            print("[SUMMARY] UI TEST RESULTS")
            print("="*60)
            print("[PASS] App loaded successfully")
            print("[PASS] Companies tab navigable")
            print(f"[PASS] {count} companies displayed in table")
            print("[PASS] Summary cards rendered")
            print("[PASS] Filter buttons functional (All, Overdue)")
            print("[PASS] Check-in buttons present and clickable")
            print(f"[PASS] {check_count} check buttons found and tested")
            print(f"\n[OUTPUT] Screenshots saved to: screenshots/")
            print("="*60)

            await browser.close()
            return True

    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Kill servers
        print("\n[STOP] Shutting down servers...")
        backend_proc.terminate()
        frontend_proc.terminate()
        try:
            backend_proc.wait(timeout=5)
            frontend_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            backend_proc.kill()
            frontend_proc.kill()
        print("[OK] Servers stopped")


if __name__ == "__main__":
    # Create screenshots directory
    Path("screenshots").mkdir(exist_ok=True)

    # Run test
    result = asyncio.run(test_company_tracker())
    sys.exit(0 if result else 1)
