import requests
from bs4 import BeautifulSoup

def get_drug_info(name):
    url = f'https://drugs.com/{name}.html'
    resp = requests.get(url)
    soup = BeautifulSoup(resp.content,'html.parser')
    elem = soup.find()
    print(elem.prettify())
    

if __name__ == '__main__':
    name = input("Enter Drug: ")
    get_drug_info(name)