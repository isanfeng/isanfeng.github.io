#!/usr/bin/python
# -*- encoding: utf-8 -*-

import time
import sys
from selenium import webdriver
from selenium.webdriver.firefox.options import Options


def deploy_gitee():
    # 模拟浏览器打开到gitee登录界面
    firefox_options = Options()
    firefox_options.add_argument("--headless")
    firefox_options.add_argument("window-size=1366x768")
    driver = webdriver.Firefox(options=firefox_options)
    # driver = webdriver.Firefox()
    driver.get('https://gitee.com/login')
    # 将窗口最大化 无头浏览器无法最大化，需要在配置中设置窗口大小
    # driver.maximize_window()
    driver.implicitly_wait(10)

    username_element = driver.find_element_by_id("user_login")
    username_element.send_keys("iwangsanfeng")
    password_element = driver.find_element_by_id("user_password")
    password = sys.argv[1]
    password_element.send_keys(password)
    # 在开发者工具中可以通过$("")测试css选择器 $x("")测试xpath选择器
    login_btn = driver.find_element_by_xpath("//form[@data-control='password']//input[@name='commit']")
    login_btn.click()
    time.sleep(1)

    # 进入pages部署页
    driver.get("https://gitee.com/iwangsanfeng/iwangsanfeng/pages")

    try:
        ad_btn = driver.find_element_by_class_name("close-icon")
        ad_btn.click()
    except:
        pass

    update_deploy_btn = driver.find_element_by_class_name("update_deploy")
    update_deploy_btn.click()

    deploy_alert = driver.switch_to.alert
    deploy_alert.accept()

    # driver.save_screenshot(f"deploy_result_{time()}.png")
    print("Deploy Completed.")
    driver.quit()


if __name__ == '__main__':
    deploy_gitee()

