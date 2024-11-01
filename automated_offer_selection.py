#-----------------------------------------------------------
# Importing Libraries
#-----------------------------------------------------------
import os
import time
import logging
import pandas as pd
import snowflake.connector

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys 
from selenium.webdriver.support import expected_conditions as EC 
from selenium.common.exceptions import WebDriverException, NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains

import logging
import sys

# Configure logging to file and stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("two_solar_bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

#-----------------------------------------------------------
# Function to initialize the driver
#-----------------------------------------------------------
def initialize_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Use headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument('--mute-audio')
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_argument("--disable-gpu")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        logger.info("Browser started successfully using Selenium Manager")
    except WebDriverException as e:
        logger.error(f"Error initializing the driver: {e}")
        driver = None
    return driver


#-----------------------------------------------------------
# Function to start the browser
#-----------------------------------------------------------
def start_browser(url):
    # Initialize the driver using the `initialize_driver` function
    driver = initialize_driver()
    if driver:
        # Navigate to the specified URL
        driver.get(url)
    else:
        logger.error("Failed to initialize the driver.")
    return driver

#-----------------------------------------------------------
# Function to handle sign-in with debug logging for each element
#-----------------------------------------------------------
def sign_in(driver, username, password):
    try:
        # Locate and interact with the username field
        logger.info("Attempting to locate the username field")
        sign_in_field = WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.XPATH, '//*[@id="form-name"]')))
        
        if sign_in_field:
            logger.info("Username field found, entering username")
            sign_in_field.send_keys(username)
        else:
            logger.error("Username field not found")
            return "Sign-in failed: Username field not found"
        
        # Locate and interact with the password field
        logger.info("Attempting to locate the password field")
        password_field = WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.XPATH, '//*[@id="login-form"]/div[2]/form/div[3]/input')))
        
        if password_field:
            logger.info("Password field found, entering password")
            password_field.send_keys(password)
        else:
            logger.error("Password field not found")
            return "Sign-in failed: Password field not found"
        
        # Locate and click the login button
        logger.info("Attempting to locate the login button")
        login_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="login-form"]/div[2]/form/input[4]')))
        
        if login_button:
            logger.info("Login button found, attempting to click")
            login_button.click()
        else:
            logger.error("Login button not found")
            return "Sign-in failed: Login button not found"

        return "The sign-in process is successfully completed"
    except TimeoutException as e:
        logger.error(f"Sign-in elements timed out: {e}")
        return f"Sign-in failed: Timeout while locating elements"
    except Exception as e:
        logger.error(f"An error occurred while signing in: {e}")
        return f"An error occurred while signing-in: {str(e)}"


#-----------------------------------------------------------
# Function to navigate to the request
#-----------------------------------------------------------
def navigating_request(driver, two_solar_id):
    try:
        # Construct the URL using the given two_solar_id
        url = f"https://app.2solar.nl/profile/rid/{two_solar_id}"
        
        # Navigate to the constructed URL
        driver.get(url)
        
        return "Navigation successful"
    except Exception as e:
        return f"An error occurred while navigating to the request: {str(e)}"

#-----------------------------------------------------------
# Function to select the offer
#-----------------------------------------------------------
def select_offer(driver):
    offer_selected = False
    try:
        table_rows = driver.find_elements(By.XPATH, '//*[@id="ajaxEditForm"]/table/tbody/tr')
        
        for row in table_rows:
            offer_content = row.find_element(By.XPATH, './td[2]').text       
            if 'offer' in offer_content.lower():                
                # Check for the presence of 'lampje' class (excluding 'lampjegreen')
                offer_button = row.find_element(By.XPATH, './td[2]//span[contains(@class, "lampje")]')
                offer_information = row.find_element(By.XPATH, './td[2]').text.strip()
                offer_button.click()
                
                # Re-check the class attribute of offer_button after the click
                offer_button_class = offer_button.get_attribute('class').lower()
                print(offer_button_class)
                if 'lampjegreen' in offer_button_class:
                    offer_selected = True
                break
                
        return offer_information, offer_selected
    
    except NoSuchElementException:
        return "There is no offer to select.", offer_selected
    except TimeoutException:
        return "Timeout occurred while waiting for elements.", offer_selected
    except Exception as e:
        return f"An error occurred while selecting the offer: {str(e)}", offer_selected

#-----------------------------------------------------------
# Main function
#-----------------------------------------------------------
def main():
    driver = None
    try:
        #-----------------------------------------------------------
        # Step 1: Retrieve the .env variables
        #-----------------------------------------------------------        
        login_url = os.getenv('TWO_SOLAR_URL')
        username = os.getenv("TWO_SOLAR_USERNAME")
        password = os.getenv("TWO_SOLAR_PASSWORD")
        
        user = os.getenv('SNOWFLAKE_USER')
        snowflake_password = os.getenv('SNOWFLAKE_PASSWORD')
        account = os.getenv('SNOWFLAKE_ACCOUNT')
        warehouse = os.getenv('SNOWFLAKE_WAREHOUSE')
        database = os.getenv('SNOWFLAKE_DATABASE')
        schema = os.getenv('SNOWFLAKE_SCHEMA')
        role = os.getenv('SNOWFLAKE_ROLE')
        
        logger.info("Successfully retrieved the .env variables")
        
        #-----------------------------------------------------------
        # Step 2: Get Snowflake data
        #-----------------------------------------------------------
        logger.info("Step 2: Get Snowflake data")
        try:
            conn = snowflake.connector.connect(
                user=user,
                password=snowflake_password,
                account=account,
                warehouse=warehouse,
                database=database,
                schema=schema,
                role=role
            )
            
            query = """
            SELECT
            a.pk_two_solar_id
            FROM warehousing_db.two_solar.fct_request as a
            LEFT JOIN warehousing_db.two_solar.dim_request as b
                ON a.pk_two_solar_id = b.pk_two_solar_id
            LEFT JOIN warehousing_db.two_solar.dim_status as c
                ON a.fk_status_id = c.pk_status_id
            LEFT JOIN warehousing_db.two_solar.fct_offer as d
                ON a.fk_offer_id = d.pk_offer_id
            WHERE
                c.status_description ILIKE '%afkeur%'
                AND c.status_description NOT ILIKE '%lead%'
                AND a.fk_offer_id IS NULL
                AND b.date_request_created > '2024-06-01'
            LIMIT 10
            """
            df = pd.read_sql(query, conn)
            conn.close()
        except Exception as e:
            logger.warning(f"An error occurred while retrieving the Snowflake data: {e}")
            return

        logger.info("Successfully retrieved the Snowflake data")
            
        #-----------------------------------------------------------
        # Step 3: Start the browser
        #-----------------------------------------------------------
        try:
            driver = start_browser(login_url)
            if driver:
                logger.info("Successfully started the browser")
            else:
                logger.error("Driver was not initialized. Exiting.")
                return
        except Exception as e:
            logger.error(f"Failed to start the browser: {str(e)}")
            return
        time.sleep(5)
        
        #-----------------------------------------------------------
        # Step 4: Sign-in process
        #-----------------------------------------------------------
        try:            
            sign_in_result = sign_in(driver, username, password)
            print(sign_in_result)
            time.sleep(5)
            if "successfully" in sign_in_result:
                logger.info(sign_in_result)
            else:
                logger.error(f"Sign-in failed: {sign_in_result}")
                return
        except Exception as e:
            logger.error(f"Sign-in process encountered an error: {str(e)}")
            return
        
        #-----------------------------------------------------------
        # Step 5: Visit request page and select the offer
        #-----------------------------------------------------------
        data = []
        for index, row in df.iterrows():
            two_solar_id = row['PK_TWO_SOLAR_ID']
            print(two_solar_id)
            try:
                navigating_request_result = navigating_request(driver, two_solar_id)
                if "successful" in navigating_request_result:
                    logger.info(f"Navigated to request {two_solar_id}")
                else:
                    logger.error(f"Failed to navigate to the request: {navigating_request_result}")
                    continue  # Skip to next request
            except Exception as e:
                logger.error(f"Failed to navigate to the request: {str(e)}")
                continue
            
            # Select the offer
            try:
                offer_information, offer_selected = select_offer(driver)
                if offer_selected:
                    logger.info(f"Offer selected for request {two_solar_id}: {offer_information}")
                    data.append({'two_solar_id': two_solar_id, 'Offer selected': offer_information})
                else:
                    logger.info(f"Offer not selected for request {two_solar_id}: {offer_information}")
                    data.append({'two_solar_id': two_solar_id, 'Offer not selected': offer_information})
            except Exception as e:
                logger.error(f"Failed to select the offer for request {two_solar_id}: {str(e)}")
                data.append({'two_solar_id': two_solar_id, 'Offer not selected': str(e)})
        
        df_result = pd.DataFrame(data)
        return df_result

    except WebDriverException as e:
        logger.error(f"WebDriver error: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
    finally:
        if driver:
            logger.info("The test has run successfully. Closing the browser")
            driver.quit()

if __name__ == "__main__":
    df_result = main()


