from langchain.tools import tool
import requests
import os
from bs4 import BeautifulSoup
from tavily import TavilyClient
from rich import print
from dotenv import load_dotenv
load_dotenv()

tavily = TavilyClient(api_key = os.getenv("TAVILY_API_KEY"))

@tool
def web_search(query: str) -> str:
    """Perform a web search for recent and reliable information and return the top results's titles,urls,snippets."""
    result = tavily.search(query=query, num_results=5)
    out =[]
    for r in result['results']:
        out.append(
            f"Title: {r['title']}\nURL: {r['url']}\nSnippet: {r['content'][:300]}\n"
        )
    return "\n---\n".join(out)

#print(web_search.invoke("What is the latest news of war?"))

@tool
def scrape_url(url:str)->str:
    """Scrape the content of a given URL and return the text for deeper reading."""
    try:
        response = requests.get(url,timeout=8,headers={'User-Agent': 'Mozilla/5.0 '})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        for tag in soup(['script', 'style','nav','footer']):
            tag.decompose()
        return soup.get_text(separator=" ",strip=True)[:3000]
    except Exception as e:
        return f"Error scraping {url}: {str(e)}"
    
#print(scrape_url.invoke("https://www.bbc.com/news/war-in-ukraine"))