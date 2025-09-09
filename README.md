# Unity Care Clinic - AI Triage & Booking Assistant

A modern, accessible chat interface for medical appointment booking and triage assistance. Built with FastAPI backend and pure HTML/CSS/JS frontend.

## ✨ Features

### 🎨 Visual & UX Improvements
- **Modern Design System**: 8px spacing scale, consistent design tokens, light/dark theme support
- **Typography**: 16px base font with 1.6 line-height for optimal readability
- **Responsive Layout**: 820px max-width on desktop, mobile-optimized with safe-area padding
- **Message Bubbles**: 640px max-width, improved contrast and spacing
- **Auto-resizing Input**: Smart textarea that grows up to 3 lines max

### 💬 Chat Experience
- **Streaming Responses**: Real-time token streaming for faster perceived performance
- **Message Grouping**: Consecutive messages grouped by sender with timestamps
- **Smart Suggestions**: Context-aware action chips for common tasks
- **Language Support**: English and Roman Urdu with automatic translation
- **Session Persistence**: Resume previous conversations with localStorage

### 🏥 Medical Features
- **Doctor Cards**: Compact cards showing avatar, name, specialty, fees, and availability
- **Date Tabs**: Today, Tomorrow, and specific dates with horizontal scrolling on mobile
- **Slot Selection**: Visual time slot chips in 3-4 column grid
- **Booking Flow**: Step-by-step appointment booking with confirmation
- **Success Cards**: Beautiful confirmation cards with calendar integration

### ♿ Accessibility
- **Keyboard Navigation**: Tab through chips, Esc to clear, Cmd/Ctrl+K to focus
- **Screen Reader Support**: ARIA labels, semantic HTML, focus management
- **High Contrast**: 4.5:1 contrast ratio maintained across themes
- **Focus Indicators**: Visible focus rings for all interactive elements

### 🔧 Technical Features
- **Error Handling**: Graceful retry with exponential backoff
- **Analytics**: Event tracking for user interactions and system performance
- **Security**: No secrets in browser, HTTPS communication with backend
- **Performance**: Optimized rendering, minimal reflows, efficient DOM updates

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- OpenAI API key
- Google Calendar API credentials (for booking)
- SMTP credentials (for email notifications)

### Installation

1. **Clone and setup**:
```bash
git clone <repository>
cd triage-mcp
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure environment**:
```bash
cp config.env.example config.env
# Edit config.env with your API keys and settings
```

3. **Run the application**:
```bash
python -m uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

4. **Access the interface**:
   - Open http://localhost:8000 in your browser
   - The chat interface will load automatically

## 🎯 Usage Examples

### Basic Triage
```
User: "I have a headache"
Assistant: "I can help you find a doctor for your headache. Let me search for available specialists..."
```

### Appointment Booking
```
User: "Book an appointment with Dr. Smith tomorrow"
Assistant: "I found Dr. Smith's available slots for tomorrow:
- 10:00 AM
- 2:30 PM
- 4:15 PM
Which time works for you?"
```

### Language Support
```
User: "Mujhe bukhar hai" (Roman Urdu for "I have fever")
Assistant: "I understand you have a fever. Let me find appropriate doctors for you..."
```

## 🏗️ Architecture

### Frontend (static/chat.html)
- **Pure HTML/CSS/JS**: No build process, no frameworks
- **Design Tokens**: CSS custom properties for consistent theming
- **Component System**: Reusable doctor cards, date tabs, success cards
- **State Management**: Simple localStorage for session persistence

### Backend (api.py)
- **FastAPI**: Modern async web framework
- **MCP Integration**: Model Context Protocol for tool calling
- **Streaming**: Server-sent events for real-time responses
- **Error Handling**: Retry logic with exponential backoff

### MCP Server (server.py)
- **Google Calendar**: Appointment scheduling and availability
- **SMTP**: Email notifications and confirmations
- **Doctor Database**: JSON-based doctor directory with condition mapping

## 🎨 Design System

### Colors
```css
/* Light Theme (Default) */
--bg: #f5f7ff
--text: #0a0f1f
--brand: #7c9cff
--border: #e3e8ff

/* Dark Theme */
--bg: #0a0f1f
--text: #e9edff
--brand: #7c9cff
--border: #26305f
```

### Spacing Scale
```css
--spacing-xs: 4px
--spacing-sm: 8px
--spacing-md: 16px
--spacing-lg: 24px
--spacing-xl: 32px
```

### Border Radius
```css
--radius-sm: 8px
--radius-md: 12px
--radius-lg: 16px
```

## 📊 Analytics Events

The system tracks these events for monitoring and improvement:

- `message_sent`: User sends a message
- `response_received`: Assistant responds successfully
- `doctor_lookup`: Doctor search performed
- `slots_shown`: Available time slots displayed
- `booking_success`: Appointment booked successfully
- `error_occurred`: System errors with retry attempts

## 🔒 Privacy & Security

- **No Sensitive Data**: Medical information not stored permanently
- **Session Isolation**: Each chat session is independent
- **HTTPS Only**: All communication encrypted in production
- **Minimal Logging**: Only essential analytics data collected
- **User Control**: Clear privacy policy and data deletion options

## 🚀 Deployment

### Render (Recommended)
1. Connect your GitHub repository
2. Set environment variables in Render dashboard
3. Deploy with Python runtime
4. Configure custom domain and SSL

### Other Platforms
- **Heroku**: Add `Procfile` with `web: uvicorn api:app --host 0.0.0.0 --port $PORT`
- **Railway**: Direct deployment from GitHub
- **DigitalOcean**: App Platform with Python runtime

## 🧪 Testing

### Manual Testing
```bash
# Start the server
python -m uvicorn api:app --reload

# Test streaming endpoint
python test_streaming.py

# Open browser to http://localhost:8000
```

### Automated Testing
```bash
# Run API tests
pytest test_api.py

# Run frontend tests
npm test  # If using testing framework
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Emergency**: Call 1122 (Pakistan emergency services)
- **Technical Issues**: Contact clinic IT support
- **Appointment Changes**: Use chat interface or call clinic directly
- **Privacy Concerns**: Review privacy policy or contact clinic management

---

Built with ❤️ for Unity Care Clinic
