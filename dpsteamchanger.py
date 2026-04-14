r"""
Steam Account Email Changer

  __            
 /\ \           
 \_\ \  _____   
 /'_` \/\ '__`\ 
/\ \L\ \ \ \L\ \
\ \___,_\ \ ,__/
 \/__,_ /\ \ \/ 
          \ \_\ 
           \/_/
"""

import csv
import re
import time
import os
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.chrome.options import Options

# ==============================================================================
# CONFIGURATION & GLOBAL LOCATORS
# ==============================================================================
WAIT_TIMEOUT = 25
OUTLOOK_WAIT = 30
MAX_POLLS = 15

# Centralized Locators for easy updating if UI changes
LOCATORS = {
    "outlook": {
        "login_email": (By.XPATH, "//input[@name='loginfmt' or @id='usernameEntry' or @type='email']"),
        "login_pass": (By.XPATH, "//input[@name='passwd' or @id='passwordEntry' or @type='password']"),
        "login_submit": (By.XPATH, "//button[@type='submit'] | //input[@type='submit'] | //*[@id='idSIButton9'] | //*[@data-testid='primaryButton']"),
        "inbox_items": (By.XPATH, "//div[@role='option'] | //div[@tabindex='-1' and contains(@draggable, 'true')]"),
        "reading_pane": (By.XPATH, "//div[@role='main'] | //div[contains(@aria-label, 'Reading Pane')] | //div[contains(@class, 'BodyFragment')]")
    },
    "steam": {
        "login_user": (By.CSS_SELECTOR, "div._2GBWeupzdtXZtnal2a1AL input[type='text'], input[type='text']"),
        "login_pass": (By.CSS_SELECTOR, "input[type='password']"),
        "login_submit": (By.XPATH, "//button[@type='submit']"),
        "login_success": (By.XPATH, "//*[@id='account_pulldown'] | //img[contains(@class, 'avatar')]"),
        "steam_guard_prompt": (By.XPATH, "//div[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'email authenticator')] | //div[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'check your email')] | //*[contains(@class, 'twofactor')]"),
        "steam_guard_inputs": (By.XPATH, "//input[contains(@class, 'segment')] | //input[@type='text' and @maxlength='5'] | //input[@type='text' and @maxlength='1']"),
        "change_email_btn": (By.XPATH, "//a[contains(@class, 'help_wizard_button') and .//span[contains(text(), 'Email')]] | //*[contains(text(), 'Email an account verification code to')] | //div[contains(@class, 'help_wizard_button')]"),
        "code_input": (By.XPATH, "//input[@maxlength='5' or @id='account_recovery_code_input' or @id='forgot_login_code' or @id='email_change_code' or @name='code' or contains(@class, 'twofactor')]"),
        "continue_btn": (By.XPATH, "//button[span[contains(text(), 'Continue')]] | //input[@type='submit' and (@value='Continue' or @value='Confirm Email Change')] | //input[contains(@class, 'help_site_button') and @type='submit']"),
        "new_email_input": (By.XPATH, "//input[@id='email_reset' or @id='email' or @type='email']"),
        "change_email_submit": (By.XPATH, "//button[span[contains(text(), 'Change Email')]] | //input[@type='submit' and @value='Change Email']"),
        "success_text": (By.XPATH, "//*[contains(@class,'help_page_title') and (contains(text(),'successfully') or contains(text(),'Success') or contains(text(),'updated') or contains(text(),'changed'))] | //div[@id='wizard_contents']//*[contains(text(),'Email address changed')]")
    }
}

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def log(level, message):
    """Standardized CLI logging."""
    prefix = ""
    if level == "INF": prefix = "[*]"
    elif level == "SUC": prefix = "[+]"
    elif level == "WRN": prefix = "[!]"
    elif level == "ERR": prefix = "[-]"
    print(f"{prefix} {message}")

def human_typing(element, text):
    """Types characters with randomized human-like delays."""
    element.clear()
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.04, 0.12))

def human_delay(min_sec=0.5, max_sec=1.5):
    """Randomized delay between actions."""
    time.sleep(random.uniform(min_sec, max_sec))

# ==============================================================================
# SELENIUM CORE
# ==============================================================================

def create_isolated_driver():
    """Create an isolated Chrome incognito session with anti-bot cloaking."""
    chrome_options = Options()
    chrome_options.add_argument("--incognito")
    chrome_options.add_argument("--window-size=1200,800")
    
    # Evasion techniques
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=chrome_options)
    
    # CDP cloaking
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver

def save_error_screenshot(driver, context_name):
    """Graceful error reporting via screenshot and HTML dump."""
    timestamp = int(time.time())
    img_filename = f"error_{context_name}_{timestamp}.png"
    html_filename = f"error_{context_name}_{timestamp}.html"
    try:
        driver.save_screenshot(img_filename)
        with open(html_filename, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        log("ERR", f"Dumped error context to: {img_filename} & {html_filename}")
    except WebDriverException:
        pass

# ==============================================================================
# WORKFLOW FUNCTIONS
# ==============================================================================

def fetch_latest_steam_code_from_outlook(email_user, email_pass, seen_codes=None):
    """Log into Outlook via browser and extract the Steam verification code."""
    if seen_codes is None:
        seen_codes = set()
    log("INF", f"[Outlook] Opening browser session for: {email_user}")
    driver = create_isolated_driver()
    wait = WebDriverWait(driver, OUTLOOK_WAIT)
    code = None

    try:
        # Navigate to Outlook landing page to build cookies
        driver.get("https://outlook.live.com/owa/")
        time.sleep(1)
        # Navigate to the actual login telemetry link
        driver.get("https://go.microsoft.com/fwlink/p/?LinkID=2125442&deeplink=mail%2F")

        # Step 1: Enter email
        email_input = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//input[@name='loginfmt' or @type='email']")
        ))
        human_typing(email_input, email_user)
        wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[@type='submit'] | //*[@id='idSIButton9']")
        )).click()

        # Step 2: Enter password
        pass_input = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//input[@name='passwd' or @type='password']")
        ))
        human_typing(pass_input, email_pass)
        wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[@type='submit'] | //*[@id='idSIButton9']")
        )).click()

        # Step 3: Handle "Stay signed in?" — click No to avoid extra prompts
        try:
            no_btn = WebDriverWait(driver, 6).until(EC.element_to_be_clickable(
                (By.XPATH, "//*[@id='idBtn_Back'] | //button[contains(text(),'No')]")
            ))
            no_btn.click()
        except TimeoutException:
            # May have auto-skipped or already redirected
            pass

        # Step 4: Wait for auto-redirect to the actual Outlook inbox
        # DO NOT manually navigate — let Microsoft complete the redirect
        log("INF", "[Outlook] Waiting for auto-redirect to inbox...")
        try:
            wait.until(lambda d: "outlook.live.com/mail" in d.current_url)
            log("SUC", f"[Outlook] Inbox reached: {driver.current_url[:60]}")
        except TimeoutException:
            # If auto-redirect didn't happen, check for errors
            page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
            if "bad user credential" in page_text or "authenticationfailed" in page_text:
                raise Exception("Microsoft rejected credentials.")
            log("WRN", f"[Outlook] Auto-redirect timed out, current URL: {driver.current_url[:80]}")
            # Try manual navigation as last resort
            driver.get("https://outlook.live.com/mail/0/")
            time.sleep(3)

        # Step 5: Poll inbox for Steam email
        log("INF", "[Outlook] Polling inbox for Steam emails...")
        for attempt in range(MAX_POLLS):
            try:
                # Look for email rows containing "steam"
                rows = driver.find_elements(By.XPATH,
                    "//div[@role='option'] | //div[@tabindex='-1' and @draggable]"
                )
                for row in rows[:10]:
                    try:
                        if "steam" in row.text.lower():
                            log("INF", "[Outlook] Steam email found. Opening...")
                            row.click()
                            time.sleep(2)

                            # Read the reading pane body
                            body_text = ""
                            for selector in [
                                "//div[@role='main']",
                                "//div[contains(@class,'BodyFragment')]",
                                "//div[contains(@class,'ReadingPane')]",
                                "//div[@aria-label='Message body']"
                            ]:
                                els = driver.find_elements(By.XPATH, selector)
                                body_text += " ".join(e.text for e in els)

                            match = re.search(r'\b([A-Z0-9]{5})\b', body_text)
                            if match:
                                code = match.group(1)
                                if code in seen_codes:
                                    log("WRN", f"[Outlook] Skipping already-processed code: {code}")
                                    
                                    # Still try to delete it to clean up the inbox
                                    try:
                                        driver.find_element(By.XPATH,
                                            "//button[@aria-label='Delete'] | //button[contains(@title,'Delete')]"
                                        ).click()
                                    except Exception:
                                        pass
                                    continue
                                
                                log("SUC", f"[Outlook] Code extracted: {code}")
                                seen_codes.add(code)
                                # Delete email to prevent stale code reuse
                                try:
                                    driver.find_element(By.XPATH,
                                        "//button[@aria-label='Delete'] | //button[contains(@title,'Delete')]"
                                    ).click()
                                except Exception:
                                    pass
                                return code
                    except Exception:
                        continue
            except Exception:
                pass

            log("INF", f"[Outlook] No Steam email yet. Retrying ({attempt+1}/{MAX_POLLS})...")
            time.sleep(5)
            if attempt % 3 == 2:
                driver.refresh()
                time.sleep(3)

    except Exception as e:
        log("ERR", f"[Outlook] Session failure: {str(e)}")
        save_error_screenshot(driver, "outlook_crash")
    finally:
        driver.quit()

    return code



def change_steam_email(steam_user, steam_pass, current_email, current_pass, new_email, new_pass):
    print("\n" + "="*50)
    log("INF", f"Initiating Processing Block: {steam_user}")
    log("INF", f"Route: {current_email} -> {new_email}")
    print("="*50)
    
    driver = create_isolated_driver()
    wait = WebDriverWait(driver, WAIT_TIMEOUT)
    seen_codes = set()
    
    try:
        log("INF", "[Steam] Generating frontend login constraints...")
        driver.get("https://steamcommunity.com/login/home/")
        
        user_input = wait.until(EC.element_to_be_clickable(LOCATORS["steam"]["login_user"]))
        human_typing(user_input, steam_user)
        
        pass_input = wait.until(EC.element_to_be_clickable(LOCATORS["steam"]["login_pass"]))
        human_typing(pass_input, steam_pass)
        
        human_delay()
        driver.find_element(*LOCATORS["steam"]["login_submit"]).click()
        
        log("INF", "[Steam] Authenticating. Awaiting SteamGuard context...")
        
        # Checking for Steam Guard vs Clean Login
        try:
            wait.until(EC.presence_of_element_located((By.XPATH, 
                "//*[@id='account_pulldown'] | //img[contains(@class, 'avatar')] | "
                "//input[@maxlength='5'] | //input[contains(@class, 'twofactor')] | "
                "//div[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'authenticator')]"
            )))
        except TimeoutException:
            pass # DOM load might be slow, fallback to raw checks
            
        time.sleep(2) # Ensure DOM settles
        
        page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        guard_inputs = driver.find_elements(By.XPATH, "//input[@maxlength='5'] | //input[contains(@class, 'twofactor')] | //input[contains(@class, 'segment')]")
        
        is_steam_guard = bool(guard_inputs) or ("authenticator" in page_text) or ("check your email" in page_text)
        
        if is_steam_guard:
            log("WRN", "[Steam] SteamGuard active. Re-routing payload to Outlook proxy...")
            sg_code = fetch_latest_steam_code_from_outlook(current_email, current_pass, seen_codes)
            if not sg_code:
                raise Exception("Failed to harvest the Steam Guard authorization token.")
                
            log("INF", "[Steam] Pushing Guard code to Steam input handlers...")
            try:
                if guard_inputs and len(guard_inputs) == 5:
                    # Segmented input (1 char each)
                    for i, char in enumerate(sg_code):
                        guard_inputs[i].send_keys(char)
                        time.sleep(random.uniform(0.01, 0.05))
                elif guard_inputs:
                    # Single input
                    guard_inputs[0].send_keys(sg_code)
                else:
                    # Ghost input (focused but unselectable via class)
                    webdriver.ActionChains(driver).send_keys(sg_code).perform()
            except Exception:
                webdriver.ActionChains(driver).send_keys(sg_code).perform()
                
            human_delay(1.0, 1.5)
            webdriver.ActionChains(driver).send_keys(Keys.ENTER).perform()
        
        log("INF", "[Steam] Awaiting successful login resolution...")
        wait.until(EC.presence_of_element_located(LOCATORS["steam"]["login_success"]))
        log("SUC", "[Steam] Access Granted.")

        # Email Change Wizard
        log("INF", "[Steam] Accessing backend Change Email Wizard...")
        driver.get("https://help.steampowered.com/en/wizard/HelpChangeEmail")
        human_delay(1.5, 2.5)
        
        # Handle secondary login if Steam prompts for it
        if "/login" in driver.current_url.lower():
            log("INF", "[Steam] Secondary login prompt detected. Authenticating...")
            sec_user_input = wait.until(EC.element_to_be_clickable(LOCATORS["steam"]["login_user"]))
            human_typing(sec_user_input, steam_user)
            
            sec_pass_input = wait.until(EC.element_to_be_clickable(LOCATORS["steam"]["login_pass"]))
            human_typing(sec_pass_input, steam_pass)
            
            driver.find_element(*LOCATORS["steam"]["login_submit"]).click()
            human_delay(3.0, 5.0)  # Give Steam time to process secondary login
            
            # Check if Steam Guard triggers AGAIN
            sec_page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
            sec_guard_inputs = driver.find_elements(By.XPATH, "//input[@maxlength='5'] | //input[contains(@class, 'twofactor')] | //input[contains(@class, 'segment')]")
            if bool(sec_guard_inputs) or "authenticator" in sec_page_text or "check your email" in sec_page_text:
                log("WRN", "[Steam] Secondary SteamGuard active...")
                sg_code2 = fetch_latest_steam_code_from_outlook(current_email, current_pass, seen_codes)
                if not sg_code2:
                    raise Exception("Failed secondary Steam Guard fetch.")
                
                if len(sec_guard_inputs) == 5:
                    for i, char in enumerate(sg_code2):
                        sec_guard_inputs[i].send_keys(char)
                elif len(sec_guard_inputs) > 0:
                    sec_guard_inputs[0].clear()
                    human_typing(sec_guard_inputs[0], sg_code2)
                else:
                    webdriver.ActionChains(driver).send_keys(sg_code2).perform()

                human_delay(1.0, 1.5)
                webdriver.ActionChains(driver).send_keys(Keys.ENTER).perform()
                wait.until(lambda d: "/login" not in d.current_url.lower())
                human_delay()

        log("INF", f"[Steam] Executing Stage 1 Auth Request against {current_email}...")
        try:
            send_code_btn = wait.until(EC.element_to_be_clickable(LOCATORS["steam"]["change_email_btn"]))
            send_code_btn.click()
        except TimeoutException:
            log("WRN", "[Steam] Stage 1 Button missing; assuming form pre-loaded.")
        
        log("INF", "[Steam] Stage 1 Request Sent.")
        
        first_code = fetch_latest_steam_code_from_outlook(current_email, current_pass, seen_codes)
        if not first_code:
            raise Exception("Outlook proxy failed on Stage 1.")
            
        log("INF", "[Steam] Posting Stage 1 Code...")
        code_input = wait.until(EC.element_to_be_clickable(LOCATORS["steam"]["code_input"]))
        code_input.clear()
        human_typing(code_input, first_code)
        
        human_delay()
        continue_btn = wait.until(EC.element_to_be_clickable(LOCATORS["steam"]["continue_btn"]))
        continue_btn.click()
        
        # New Email Stage
        log("INF", f"[Steam] Committing new target: {new_email}...")
        new_email_input = wait.until(EC.element_to_be_clickable(LOCATORS["steam"]["new_email_input"]))
        human_typing(new_email_input, new_email)
        
        human_delay()
        wait.until(EC.element_to_be_clickable(LOCATORS["steam"]["change_email_submit"])).click()
        
        log("INF", f"[Steam] Executing Stage 2 Auth Request against {new_email}...")
        log("INF", "[Steam] Waiting for Stage 2 code input field...")
        wait.until(EC.element_to_be_clickable(LOCATORS["steam"]["code_input"]))
        
        second_code = fetch_latest_steam_code_from_outlook(new_email, new_pass, seen_codes)
        if not second_code:
            raise Exception("Outlook proxy failed on Stage 2.")
            
        log("INF", "[Steam] Posting Stage 2 Code...")
        new_code_input = wait.until(EC.element_to_be_clickable(LOCATORS["steam"]["code_input"]))
        new_code_input.clear()
        human_typing(new_code_input, second_code)
        
        human_delay()
        continue_btn = wait.until(EC.element_to_be_clickable(LOCATORS["steam"]["continue_btn"]))
        continue_btn.click()
        
        log("INF", "[Steam] Validating deployment...")
        # Success: wizard either shows confirmation text or navigates away from code entry
        def is_success(d):
            url = d.current_url.lower()
            body = d.find_element(By.TAG_NAME, "body").text.lower()
            return (
                "helpwithlogininforesult" in url
                or "email address changed" in body
                or "successfully" in body
                or ("HelpChangeEmail" not in d.current_url and "email_change_code" not in body)
            )
        wait.until(is_success)
        log("SUC", f"[Steam] Migration to {new_email} completed perfectly.")
        return True
        
    except TimeoutException:
        log("ERR", "[Steam] Timed out waiting for page elements. Possible Steam layout variation.")
        save_error_screenshot(driver, "steam_timeout")
        return False
    except Exception as e:
        log("ERR", f"[Steam] Unexpected sequence failure: {str(e)}")
        save_error_screenshot(driver, "steam_crash")
        return False
        
    finally:
        driver.quit()

# ==============================================================================
# DATA PIPELINE
# ==============================================================================

def main():
    log("INF", "Booting DP Steam Changer Pipeline")
    if not os.path.exists("accounts.csv"):
        log("ERR", "Mapping failure: 'accounts.csv' not found in working directory.")
        return
        
    if not os.path.exists("new_emails.csv"):
        log("WRN", "Mapping failure: 'new_emails.csv' not found. Creating blank template.")
        with open("new_emails.csv", "w", newline="", encoding="utf-8") as f:
            f.write("new_email,new_email_password\n")
        log("INF", "Please fill out 'new_emails.csv' and restart.")
        return

    with open("accounts.csv", "r", encoding="utf-8") as f:
        accounts_lines = list(csv.reader(f))
    if accounts_lines and 'steam_user' in accounts_lines[0][0].lower():
        accounts_lines = accounts_lines[1:]
        
    with open("new_emails.csv", "r", encoding="utf-8") as f:
        new_emails_lines = list(csv.reader(f))
    if new_emails_lines and 'new_email' in new_emails_lines[0][0].lower():
        new_emails_lines = new_emails_lines[1:]
        
    if len(accounts_lines) > len(new_emails_lines):
        log("WRN", f"Imbalanced configuration: {len(accounts_lines)} old accounts vs {len(new_emails_lines)} new emails.")
        log("WRN", f"Only the first {len(new_emails_lines)} rows will be processed.")
        
    results = []
    
    for account_row, new_email_row in zip(accounts_lines, new_emails_lines):
        if len(account_row) < 4 or len(new_email_row) < 2:
            log("ERR", "Malformed CSV row detected. Bypassing...")
            continue
            
        steam_user, steam_pass, current_email, current_pass = [x.strip() for x in account_row[:4]]
        new_email, new_pass = [x.strip() for x in new_email_row[:2]]
        
        success = change_steam_email(
            steam_user, steam_pass, 
            current_email, current_pass, 
            new_email, new_pass
        )
        
        results.append([steam_user, current_email, new_email, "Success" if success else "Failed"])
        
        if success:
            log("INF", "Initiating 5s cooldown cycle to bleed rate limiting...")
            time.sleep(5)
            
    with open("results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Steam Username", "Old Email", "New Email", "Status"])
        writer.writerows(results)

    print("\n" + "="*50)
    log("SUC", "Batch Processing Complete. Report saved to 'results.csv'.")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()