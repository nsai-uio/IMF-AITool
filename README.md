# IMF-AITool

A LLM based web application for automatic IMF modelling tool.

# Install
install python
```conda create -n imf_web pip python=3.9```   

install packages
```pip install Flask, Werkzeug, json, thread, uuid-utils, python-dotenv, PyPDF2```

```pip install google-generativeai```

# set up environment variables locally for API key (Mac)
1. open your configuration file:
```nano ~/.zshrc```
2. Add this line, then save and exit:
```export GOOGLE_API_KEY="Your API Key"```
3. source the configuration file:
```source ~/.zshrc```


# Run
```python app.py```