from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time

service = Service()
options = webdriver.EdgeOptions()
driver = webdriver.Edge(service=service, options=options)

USERNAME = "performance_glitch_user"
PASSWORD = "secret_sauce"
SORT_OPTION = "za"
ADD_FIRST_PRODUCT = True
ACTION_CART = "add_and_return"

URL = "https://www.saucedemo.com/"

try:
    driver.get(URL)
    print("Открыта страница входа.")

    username_field = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "user-name"))
    )
    password_field = driver.find_element(By.ID, "password")

    username_field.send_keys(USERNAME)
    password_field.send_keys(PASSWORD)
    print("Логин и пароль введены.")
    time.sleep(3)

    login_button = driver.find_element(By.ID, "login-button")
    login_button.click()
    print("Нажата кнопка входа.")

    try:
        error_message = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, "//*[contains(@class, 'error-message') or contains(text(), 'locked')]"))
        )
        if "locked" in error_message.text.lower():
            print(f"Пользователь {USERNAME} заблокирован. Используем резервного пользователя.")
            USERNAME = "standard_user"
            driver.get(URL)
            username_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "user-name"))
            )
            username_field.send_keys(USERNAME)
            driver.find_element(By.ID, "password").send_keys(PASSWORD)
            driver.find_element(By.ID, "login-button").click()
    except TimeoutException:
        pass

    try:
        WebDriverWait(driver, 10).until(
            EC.url_contains("inventory.html")
        )
    except TimeoutException:
        print("Не удалось авторизоваться.")
        raise

    sort_dropdown = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CLASS_NAME, "product_sort_container"))
    )
    sort_select = Select(sort_dropdown)
    sort_select.select_by_value(SORT_OPTION)
    print("Товары отсортированы по имени (Z to A).")
    time.sleep(3)

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "inventory_item"))
    )
    products = driver.find_elements(By.CLASS_NAME, "inventory_item")
    print(f"Найдено товаров: {len(products)}")

    if len(products) == 0:
        print("Товары не найдены!")
        exit()

    if ADD_FIRST_PRODUCT:
        # Находим кнопку "Add to cart" у первого товара
        first_product = products[0]
        add_button = first_product.find_element(By.TAG_NAME, "button")
        product_name = first_product.find_element(By.CLASS_NAME, "inventory_item_name").text
        add_button.click()
        print(f"Товар '{product_name}' добавлен в корзину.")
        time.sleep(3)

    if ACTION_CART == "add_and_return":
        cart_badge = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "shopping_cart_link"))
        )
        cart_badge.click()
        print("Переход в корзину.")
        time.sleep(3)

        item_in_cart = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "cart_item"))
        )
        print("Товар присутствует в корзине.")
        time.sleep(3)

        continue_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "continue-shopping"))
        )
        continue_button.click()
        print("Возврат в каталог.")

    time.sleep(3)

except Exception as e:
    print(f"Произошла ошибка: {e}")
finally:
    driver.quit()
    print("Браузер закрыт.")
