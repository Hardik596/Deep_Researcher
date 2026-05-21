from agents import build_search_agent, build_scrape_agent, writer_chain, critic_chain
import time

def invoke_with_retry(agent_or_chain, input_dict, retries=4, wait=60):
    """Retry on 429 rate limit errors with exponential-ish backoff."""
    for attempt in range(retries):
        try:
            return agent_or_chain.invoke(input_dict)
        except Exception as e:
            if "429" in str(e) and attempt < retries - 1:
                backoff = wait * (attempt + 1)  # 60s, 120s, 180s...
                print(f"\n⚠️  Rate limited. Waiting {backoff}s before retry {attempt + 1}/{retries - 1}...")
                time.sleep(backoff)
            else:
                raise
            
def run_research_pipeline(topic : str)-> dict:
    
    state = {}


    #search agent working
    print("\n"+" ="*50)
    print("Step 1 - Running Search Agent...")
    print(" ="*50)

    search_agent = build_search_agent()
    search_result = search_agent.invoke({
        "messages":[{"role":"user","content":f"Find recent, reliable and detailed information about: {topic}"}]
    })
    state["search_result"] = search_result["messages"][-1].content
    print("\n Search Agent Output:", state["search_result"])
    time.sleep(5)
    print("\n"+" ="*50)
    print("Step 2 - Running Scrape Agent...")
    print(" ="*50)
    scrape_agent = build_scrape_agent()
    scrape_result = scrape_agent.invoke({
         "messages":[{
             "role": "user",
             "content": f"Based on the following search results about '{topic}'"
             f"pick the most relevant URLs and scrape it for deeper content. \n\n"
             f"Search Results:\n{state['search_result'][:800]}"
         }]
        })
    state['scrapped_content'] = scrape_result['messages'][-1].content

    print("\n Scrape Agent Output:", state["scrapped_content"][:500], "...")
    time.sleep(20)
    print("\n"+" ="*50)
    print("Step 3 - Running Writer Chain...")
    print(" ="*50)

    research_combined = (
        f"SEARCH RESULTS : \n {state['search_result']} \n\n"
        f"DETAILED SCRAPED CONTENT : \n {state['scrapped_content']}"
    )


    state["report"] = invoke_with_retry(writer_chain, {
        "topic": topic,
        "research": research_combined
    })

    print("\n Final Report\n",state['report'])
    
    #critic report 
    time.sleep(20)
    print("\n"+" ="*50)
    print("step 4 - critic is reviewing the report ")
    print("="*50)

    state["feedback"] = critic_chain.invoke({
        "report":state['report']
    })

    print("\n critic report \n", state['feedback'])

    return state

if __name__ == "__main__":
    topic = input("\n Enter a research topic : ")
    run_research_pipeline(topic)