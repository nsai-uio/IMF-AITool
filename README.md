# IMF-AITool

A LLM based web application for automatic IMF modelling.

# Install 
install python
```conda create -n imf_web pip python=3.9```   

install packages
```pip install Flask, Werkzeug, json, thread, uuid-utils, python-dotenv, PyPDF2```

```pip install google-generativeai```

# Set up environment variables locally for API key (Mac)
1. Open your configuration file:
```nano ~/.zshrc```
2. Add this line, then save and exit:
```export GOOGLE_API_KEY="Your API Key"```
3. Source the configuration file:
```source ~/.zshrc```


# Run the web application
```python app_user_panel.py```

# Test with function-based scripts
1. put your test files under path: ```test_scripts/uploads```;
it will then ask you to choose one of the files to test.
2. run ```python function_test.py```