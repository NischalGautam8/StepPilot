# Gemini API Setup and Testing Guide ✅

## ✅ Gemini Integration Complete!

Google Gemini API has been successfully integrated into StepPilot as a third LLM provider option alongside GitHub Copilot and OpenAI.

---

## 🎯 What Was Added

### 1. **Gemini Provider** ✅
- **File:** `backend/llm/gemini_provider.py`
- **Models:**
  - `gemini-1.5-flash` - Fast, budget-friendly text completion
  - `gemini-1.5-pro` - Advanced multimodal vision processing
- **Features:**
  - Text completion
  - Vision completion (with screenshots)
  - Streaming support
  - JSON mode support

### 2. **Updated Orchestrator** ✅
- **File:** `backend/llm/orchestrator.py`
- **Changes:**
  - Added Gemini provider import
  - Updated `_get_provider()` to support "gemini" option
  - Maintains timeout and retry logic

### 3. **Updated Settings Manager** ✅
- **File:** `backend/core/settings_manager.py`
- **Changes:**
  - Loads GEMINI_API_KEY from .env when provider is "gemini"
  - Logs Gemini configuration

### 4. **Configuration Files** ✅
- **backend/.env:**
  ```
  LLM_PROVIDER=gemini
  GEMINI_API_KEY=AIzaSyDBEm77LTQgQVT4OHoM5ekJpNrjzwbKcDs
  ```

- **~/.cursor-king/config.json:**
  ```json
  {
    "llm_provider": "gemini",
    "model_name": "gemini-1.5-flash",
    "show_debug_overlay": false,
    "auto_advance": true,
    "hotkey": "Ctrl+Alt+K"
  }
  ```

### 5. **Dependencies** ✅
- **Added to requirements.txt:**
  ```
  google-generativeai>=0.3.0
  ```
- **Installed:** ✅ Package installed successfully

---

## 🚀 Current Status

**Backend Running with Gemini:**
```
✅ Process ID: 18780
✅ Running on http://127.0.0.1:8765
✅ LLM_PROVIDER=gemini
✅ GEMINI_API_KEY=*** (configured)
✅ WebSocket connected
```

**Frontend Running:**
```
✅ Tauri app active
✅ WebSocket connected to backend
✅ Ready to test
```

---

## 🧪 How to Test Sprint 2 with Gemini

### Test 1: Basic Text Completion
1. Open the Tauri app (already running)
2. Type a simple task in the chat: **"Open Notepad"**
3. Press Send or Enter
4. **Expected Result:**
   - Backend receives the query
   - Gemini API is called
   - Task plan is generated
   - Response appears in chat

### Test 2: Vision Completion (Screenshot Analysis)
1. Make sure a window is open (e.g., File Explorer)
2. In the app, type: **"Click the close button"**
3. Press Send
4. **Expected Result:**
   - Screenshot is captured
   - Sent to Gemini with vision (gemini-1.5-pro)
   - Elements are detected
   - Guidance overlay appears

### Test 3: Error Handling
1. Temporarily change GEMINI_API_KEY to invalid value
2. Try to send a task
3. **Expected Result:**
   - Error message appears
   - Error is copyable
   - Shows Gemini-specific error details

### Test 4: Check Logs
```powershell
# View structured logs
cat C:\Users\Rakshan\.cursor-king\logs\cursor-king.log

# Should see:
# - "Applied settings: LLM_PROVIDER=gemini"
# - "Gemini API configured successfully"
# - LLM call logs with Gemini provider
```

---

## 📊 LLM Provider Comparison

| Feature | GitHub Copilot | OpenAI | Gemini |
|---------|---------------|--------|--------|
| **Text Model** | GPT-4 | gpt-4o-mini | gemini-1.5-flash |
| **Vision Model** | GPT-4 Vision | gpt-4o | gemini-1.5-pro |
| **Cost** | $10/month | Pay-per-use | Free tier + pay-per-use |
| **Speed** | Fast | Fast | Very Fast |
| **Context** | 128K tokens | 128K tokens | 1M tokens |
| **Status** | ✅ Implemented | ✅ Implemented | ✅ Implemented |

---

## 🔧 Switching Between Providers

### Method 1: Edit config.json
```powershell
# Edit the config file
notepad C:\Users\Rakshan\.cursor-king\config.json

# Change "llm_provider" to:
# - "copilot" for GitHub Copilot
# - "openai" for OpenAI
# - "gemini" for Google Gemini

# Restart backend
```

### Method 2: Edit backend/.env
```powershell
# Edit .env file
notepad c:\Projects\StepPilot\backend\.env

# Change LLM_PROVIDER to:
# LLM_PROVIDER=gemini
# or
# LLM_PROVIDER=openai
# or
# LLM_PROVIDER=copilot

# Restart backend
```

---

## 🎯 Testing Checklist

### Sprint 2 Features to Test:

- [ ] **Screen Capture**
  - Capture screenshot on task start
  - JPEG compression working
  - Differential detection (skip unchanged frames)

- [ ] **WebSocket Bridge**
  - Rust → Python communication
  - Message protocol working
  - Reconnection on disconnect

- [ ] **OCR & Element Detection**
  - PaddleOCR detects text
  - Windows A11y detects controls
  - Element merger combines results

- [ ] **LLM Integration (Gemini)**
  - Text completion works
  - Vision completion works
  - Task planning generates steps
  - JSON mode works

- [ ] **Error Handling**
  - Timeout and retry logic
  - Copyable error messages
  - Detailed error codes

---

## 🐛 Troubleshooting

### Issue: "Gemini API key is missing"
**Solution:**
```powershell
# Check .env file
cat c:\Projects\StepPilot\backend\.env

# Should contain:
# GEMINI_API_KEY=AIzaSyDBEm77LTQgQVT4OHoM5ekJpNrjzwbKcDs

# Restart backend
```

### Issue: "Invalid API key"
**Solution:**
- Verify API key at https://makersuite.google.com/app/apikey
- Check for typos in .env file
- Ensure no extra spaces or quotes

### Issue: "Provider not switching"
**Solution:**
```powershell
# Delete config file to reset
del C:\Users\Rakshan\.cursor-king\config.json

# Restart backend - will use .env settings
```

### Issue: "Rate limit exceeded"
**Solution:**
- Gemini has generous free tier
- Check quota at https://makersuite.google.com/
- Wait a moment and retry

---

## 📝 API Key Information

### Your Gemini API Key:
```
AIzaSyDBEm77LTQgQVT4OHoM5ekJpNrjzwbKcDs
```

### Get More Keys:
- **Gemini:** https://makersuite.google.com/app/apikey
- **OpenAI:** https://platform.openai.com/api-keys
- **GitHub Copilot:** Requires subscription + local auth

---

## 🎉 Summary

**Gemini Integration: COMPLETE!**

✅ Gemini provider implemented  
✅ API key configured  
✅ Backend running with Gemini  
✅ Frontend connected  
✅ Ready to test Sprint 2  

**Next Steps:**
1. Test basic task: "Open Notepad"
2. Test vision task: "Click the close button"
3. Check logs for Gemini API calls
4. Verify error handling works

**The app is now ready to test with Gemini API!** 🚀
