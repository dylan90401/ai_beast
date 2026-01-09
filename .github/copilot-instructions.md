# GitHub Copilot Instructions for AI Beast Project

## Project Overview
This file contains coding guidelines and best practices for the AI Beast project.

## Code Style & Standards
- Use descriptive variable and function names
- Follow PEP 8 style guide for Python code
- Include docstrings for functions and classes
- Add type hints where applicable

## AI/Agent Development
- Follow AI agent development best practices
- Implement proper error handling and logging
- Use structured prompts and clear system messages
- Consider token budgets and context management

## Tracing & Observability
- Add tracing to AI operations for debugging and monitoring
- Log important state transitions and decisions
- Track token usage and API calls

## Testing & Evaluation
- Write unit tests for critical functionality
- Create evaluation metrics for AI outputs
- Maintain test datasets for consistency
- Document test scenarios and expected outcomes

## Documentation
- Keep README.md updated with setup instructions
- Document API endpoints and interfaces
- Add inline comments for complex logic
- Maintain a CHANGELOG for significant updates

## Security & API Keys
- Never commit API keys or secrets
- Use environment variables for sensitive data
- Follow principle of least privilege
- Sanitize user inputs

## Dependencies
- Pin dependency versions for reproducibility
- Keep dependencies up to date
- Document required packages in requirements.txt or pyproject.toml

## Project Structure
- Organize code into logical modules and packages
- Separate concerns (e.g., models, services, utilities)
- Keep configuration separate from application code
- Use clear directory naming conventions

## Git Workflow
- Write clear, descriptive commit messages
- Create feature branches for new work
- Keep commits focused and atomic
- Review code before merging to main

## Performance
- Optimize AI model calls to reduce latency
- Cache responses where appropriate
- Monitor memory usage for long-running operations
- Profile code to identify bottlenecks

## Error Handling
- Use try-except blocks for API calls
- Provide meaningful error messages
- Implement retry logic for transient failures
- Log errors with context for debugging