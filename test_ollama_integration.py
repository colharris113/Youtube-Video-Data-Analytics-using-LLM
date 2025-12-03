#!/usr/bin/env python3
"""
Test script to verify Ollama integration for YouTube Analyzer
"""

import requests
import json

def test_ollama_connection():
    """Test if Ollama is running and accessible"""
    try:
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code == 200:
            print("[OK] Ollama is running and accessible")
            models = response.json()
            if models.get('models'):
                print(f"Available models: {[model['name'] for model in models['models']]}")
            else:
                print("[WARN] No models found in Ollama")
            return True
        else:
            print(f"[ERROR] Ollama returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("[ERROR] Cannot connect to Ollama. Make sure it's running on localhost:11434")
        return False

def test_ollama_generate():
    """Test if Ollama can generate responses"""
    try:
        payload = {
            "model": "gpt-oss:20b",
            "prompt": "Hello, can you confirm you're working?",
            "stream": False
        }
        response = requests.post("http://localhost:11434/api/generate", json=payload)
        if response.status_code == 200:
            result = response.json()
            print(f"[OK] Ollama generation test successful")
            print(f"Response: {result.get('response', 'No response')}")
            return True
        else:
            print(f"[ERROR] Ollama generation failed with status: {response.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] Ollama generation test failed: {e}")
        return False

def test_config():
    """Test the configuration file"""
    try:
        from config import OLLAMA_BASE_URL, OLLAMA_MODEL, YOUTUBE_API_KEY
        print(f"[OK] Configuration loaded successfully")
        print(f"   OLLAMA_BASE_URL: {OLLAMA_BASE_URL}")
        print(f"   OLLAMA_MODEL: {OLLAMA_MODEL}")
        print(f"   YOUTUBE_API_KEY: {'*' * 10}{YOUTUBE_API_KEY[-4:]}")
        return True
    except ImportError as e:
        print(f"[ERROR] Configuration import failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing YouTube Analyzer Ollama Integration")
    print("=" * 50)

    # Test configuration
    config_ok = test_config()

    # Test Ollama connection
    ollama_ok = test_ollama_connection()

    # Test Ollama generation (if connection is ok)
    if ollama_ok:
        generation_ok = test_ollama_generate()
    else:
        generation_ok = False
        print("Skipping generation test due to connection failure")

    print("=" * 50)
    if config_ok and ollama_ok and generation_ok:
        print("All tests passed! Ollama integration is working correctly.")
    else:
        print("Some tests failed. Check the configuration and Ollama setup.")