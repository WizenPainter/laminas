import json
import pandas as pd
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support import expected_conditions as EC

from util_types import VIDRIO

URL_PRODUCCION = "https://vecasolutions.com/app/index.php?action=reporteador&rep=3"

def _setup_firefox() -> object:
    driver_path = '/usr/local/bin/geckodriver'
    service = Service(executable_path=driver_path)

    driver = webdriver.Firefox(service=service)
    return driver

def _login(driver) -> None:
    driver.get(URL_PRODUCCION)
    username_input = driver.find_element(By.NAME, "username")
    password_input = driver.find_element(By.NAME, "password")

    username_input.clear()
    username_input.send_keys("jaimegp")
    password_input.clear()
    password_input.send_keys("@veca123")

    login_btn =driver.find_element(By.TAG_NAME, "button")
    login_btn.click()


def get_produccion() -> pd.DataFrame:
    driver = _setup_firefox()
    _login(driver)
    df_final = pd.DataFrame(columns=["Tipo","Cliente","Ped","Lin","Pzs.","Obra","ITEM","Descripcion","Esp","Largo"
                                     ,"Ancho","Area","Corte","CPB","Ho","Te","Em","PP","Re","Ta","Av","CPB","Fecha","Fecha Entrega","Terminado","P","PP (pesos)",
                                     "Te (pesos)","Em (pesos)"])

    # Wait for the page to load
    try:
        driver.get(URL_PRODUCCION)
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        page_number = 1
        while True:
            print(f"Processing page: {page_number}")
            wait.until(EC.presence_of_element_located((By.ID, "dt_basic_cargaproduccion")))
            
            # Get current table content
            table = driver.find_element(By.ID, "dt_basic_cargaproduccion")
            current_content = table.get_attribute('innerHTML')

            # Extract table data
            soup = BeautifulSoup(current_content, "html.parser")
            data = []
            headers = [th.text.strip() for th in soup.find_all('th')]
            headers = headers[1:30]
            for row in soup.find_all('tr'):
                cells = row.find_all('td')
                if cells:
                    data.append([cell.text.strip() for cell in cells][1:30])
            
            # Create DataFrame for current page
            df = pd.DataFrame(data, columns=headers)
            df_final = pd.concat([df_final, df], ignore_index=True)

            # Check if there's a next page
            try:
                next_button = driver.find_element(By.XPATH, "//li[@class='next']/a")
                if 'disabled' in next_button.get_attribute('class'):
                    print(f"Reached last page. Finished processing ")
                    break  # No more pages
                else:
                    # Use JavaScript to click the next button
                    driver.execute_script("arguments[0].click();", next_button)
                    
                    # Wait for the table content to change
                    def table_content_changed(driver):
                        new_table = driver.find_element(By.ID, "dt_basic_cargaproduccion")
                        return new_table.get_attribute('innerHTML') != current_content

                    wait.until(table_content_changed)
                    page_number += 1
            except TimeoutException:
                print(f"Timeout waiting for next page.")
                break
            except NoSuchElementException:
                print(f"Next button not found. Finished processing")
                break  # No more pages        
        return df_final
    except TimeoutException:
        print("Timed out waiting for page to load")
        driver.quit()
        raise TimeoutError("Timed out waiting for page to load")
    finally:
        driver.quit()

import pandas as pd
import json
from typing import Dict

def reduce_to_same_glass(df: pd.DataFrame, use_existing: bool = False, return_json: bool = False, glass_map: dict = VIDRIO) -> dict[str, pd.DataFrame]:
    """
    Groups glass panels by mapped type, thickness and dimensions.
    
    Args:
        df: DataFrame with columns ['ITEM', 'Esp', 'Largo', 'Ancho', 'Pzs.']
        use_existing: Whether to use existing data or filter by Production
        glass_map: Dictionary mapping original glass types to standardized names
    Returns:
        Dictionary of DataFrames for each mapped glass type
    """
    if use_existing:
        df_vidrio = df[["ITEM", "Esp", "Largo", "Ancho", "Pzs."]].copy()
    else:
        df = df[df["P"] == "Produccion"].copy()
        df_vidrio = df[["ITEM", "Esp", "Largo", "Ancho", "Pzs."]].copy()
        # Map glass types
        df_vidrio['ITEM'] = df_vidrio['ITEM'].map(glass_map)
        
    # Create measures column
    df_vidrio['Measures'] = df_vidrio.apply(
        lambda x: f"{x['Largo']}x{x['Ancho']}", 
        axis=1
    )
    
    # Save intermediate data
    df_vidrio.to_csv("glass_data.csv", index=False)
    
    # Group by mapped glass type
    glass_types = {}
    glass_types_export = {}  # Serializable version for JSON
    
    for glass_type in df_vidrio['ITEM'].unique():
        if pd.notna(glass_type):  # Skip unmapped types
            type_df = df_vidrio[df_vidrio['ITEM'] == glass_type]
            type_df["Pzs."] = type_df["Pzs."].astype(int)
            result = type_df.groupby(['Esp', 'Measures'])['Pzs.'].sum().reset_index()
            glass_types[glass_type] = result.sort_values(['Esp', 'Measures'])
            
            # Create serializable version of the data
            glass_types_export[glass_type] = {
                'data': result.to_dict(orient='records'),
                'summary': {
                    'total_pieces': int(result['Pzs.'].sum()),
                    'unique_sizes': len(result),
                    'thickness': int(result['Esp'].iloc[0])
                }
            }
    
    # Save to JSON
    with open("glass_types.json", "w", encoding='utf-8') as f:
        json.dump(glass_types_export, f, indent=4)
    
    # Save detailed CSV files for each type
    for glass_type, df in glass_types.items():
        df.to_csv(f"glass_type_{glass_type}.csv", index=False)

    if return_json:
        return glass_types_export

    return glass_types