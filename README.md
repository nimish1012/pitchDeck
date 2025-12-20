# AI Presentation Generator

A FastAPI-based web service that generates presentations using AI from three different input methods:
1. Document upload with additional text
2. One-liner prompt
3. Pre-structured outline

## Features

- 🚀 **FastAPI Framework**: High-performance async API with automatic OpenAPI documentation
- 📄 **Multiple Input Methods**: Support for documents, prompts, and structured outlines
- 🤖 **AI-Powered Generation**: Integration-ready for various AI services (OpenAI, Anthropic, etc.)
- 📁 **File Processing**: Support for PDF, DOCX, TXT, and MD files
- 🔒 **Input Validation**: Comprehensive validation for all inputs
- 📊 **Structured Output**: Consistent presentation data structure
- 🌐 **CORS Enabled**: Ready for frontend integration

## Project Structure

```
presentation-generator/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application entry point
│   ├── api/
│   │   ├── __init__.py
│   │   └── endpoints/
│   │       ├── __init__.py
│   │       ├── presentations.py   # Main presentation endpoints
│   │       └── health.py          # Health check endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py              # Application configuration
│   ├── models/
│   │   ├── __init__.py
│   │   └── request_schemas.py     # Pydantic models for requests/responses
│   ├── services/
│   │   ├── __init__.py
│   │   ├── presentation_generator.py  # AI presentation generation logic
│   │   └── document_processor.py     # Document file processing
│   └── utils/
│       ├── __init__.py
│       ├── file_handler.py       # File upload handling
│       └── validators.py         # Input validation utilities
├── requirements.txt               # Python dependencies
├── README.md                     # This file
└── .env.example                  # Environment variables template
```

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd presentation-generator
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env file with your configuration
   ```

5. **Run the application**
   ```bash
   python app/main.py
   ```

The API will be available at `http://localhost:8000`

## API Endpoints

### Health Check
- `GET /api/v1/health` - Basic health check
- `GET /api/v1/status` - Detailed service status

### Presentation Generation

#### 1. Document Upload
```http
POST /api/v1/presentations/document
Content-Type: multipart/form-data

file: [PDF/DOCX/TXT/MD file]
title: "Optional presentation title"
additional_text: "Optional additional instructions"
theme: "default"  # or custom theme
max_slides: 10
output_format: "pptx"  # pptx, pdf, html
```

#### 2. Prompt-Based
```http
POST /api/v1/presentations/prompt
Content-Type: application/x-www-form-urlencoded

prompt: "Explain the benefits of renewable energy"
title: "Renewable Energy Benefits"
theme: "default"
max_slides: 10
output_format: "pptx"
target_audience: "general"
```

#### 3. Outline-Based
```http
POST /api/v1/presentations/outline
Content-Type: application/json

{
  "outline": [
    {
      "title": "Introduction",
      "content": ["Point 1", "Point 2"],
      "notes": "Speaker notes for introduction"
    },
    {
      "title": "Main Topic",
      "content": ["Detail 1", "Detail 2", "Detail 3"]
    }
  ],
  "title": "My Presentation",
  "theme": "default",
  "include_images": true
}
```

### Presentation Management
- `GET /api/v1/presentations/{presentation_id}` - Retrieve presentation
- `DELETE /api/v1/presentations/{presentation_id}` - Delete presentation

## Configuration

Edit `.env` file to configure:

```env
# Application Settings
APP_NAME="AI Presentation Generator"
DEBUG=true

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# AI Service Configuration
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# File Upload Settings
MAX_FILE_SIZE=10485760  # 10MB in bytes
ALLOWED_FILE_TYPES=.pdf,.docx,.txt,.md

# Database (optional)
DATABASE_URL=postgresql://user:password@localhost/dbname
```

## Usage Examples

### Using curl

#### Document Upload
```bash
curl -X POST "http://localhost:8000/api/v1/presentations/document" \
  -F "file=@document.pdf" \
  -F "title=My Presentation" \
  -F "additional_text=Make it engaging" \
  -F "max_slides=15"
```

#### Prompt-Based
```bash
curl -X POST "http://localhost:8000/api/v1/presentations/prompt" \
  -F "prompt=Introduction to machine learning algorithms" \
  -F "title=ML Algorithms Overview" \
  -F "max_slides=12"
```

#### Outline-Based
```bash
curl -X POST "http://localhost:8000/api/v1/presentations/outline" \
  -H "Content-Type: application/json" \
  -d '{
    "outline": [
      {"title": "Slide 1", "content": ["Content 1"]},
      {"title": "Slide 2", "content": ["Content 2"]}
    ],
    "title": "My Outline Presentation"
  }'
```

### Using Python requests

```python
import requests

# Document upload
with open('document.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/v1/presentations/document',
        files={'file': f},
        data={
            'title': 'My Presentation',
            'additional_text': 'Add engaging content',
            'max_slides': 10
        }
    )

# Prompt-based
response = requests.post(
    'http://localhost:8000/api/v1/presentations/prompt',
    data={
        'prompt': 'Benefits of cloud computing',
        'title': 'Cloud Computing Benefits',
        'max_slides': 8
    }
)
```

## Development

### Running Tests
```bash
pytest tests/
```

### Code Formatting
```bash
black app/
flake8 app/
```

### Adding New Features

1. **New AI Service**: Extend `BasePresentationGenerator` in `app/services/presentation_generator.py`
2. **New File Formats**: Update `DocumentProcessor` in `app/services/document_processor.py`
3. **New Validators**: Add to `app/utils/validators.py`
4. **New Endpoints**: Add to `app/api/endpoints/presentations.py`

## Production Deployment

### Docker
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ ./app/
COPY .env .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables for Production
- Set `DEBUG=false`
- Configure proper CORS origins
- Set up proper database connection
- Configure AI service API keys
- Set up file storage (S3, etc.)

## API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Check the API documentation at `/docs`
- Review the example requests above
- Create an issue in the repository

## Roadmap

- [ ] Database integration for presentation storage
- [ ] Real AI service integration (OpenAI, Anthropic)
- [ ] Template system for different presentation styles
- [ ] Image generation and integration
- [ ] Batch processing capabilities
- [ ] User authentication and management
- [ ] Presentation sharing and collaboration
- [ ] Export to multiple formats (PDF, PowerPoint, Google Slides)