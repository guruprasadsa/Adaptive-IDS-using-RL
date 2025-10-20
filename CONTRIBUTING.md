# Contributing to Adaptive IDS v2.0

Thank you for your interest in contributing to Adaptive IDS! This document provides guidelines and instructions for contributing.

## 🚀 Getting Started

1. **Fork the repository**
   ```bash
   git clone https://github.com/guruprasadsa/Adaptive-IDS-using-RL.git
   cd Adaptive-IDS-using-RL
   ```

2. **Set up your development environment**
   - Follow the [Installation Checklist](./documentation/INSTALLATION_CHECKLIST.md)
   - Ensure all tests pass before making changes

3. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

## 📝 Code Style

### Python (Backend)
- Follow PEP 8 style guidelines
- Use type hints where applicable
- Add docstrings for functions and classes
- Keep functions focused and modular
- Maximum line length: 100 characters

Example:
```python
from typing import Dict, List, Optional

def get_alert_statistics(
    user_id: int,
    time_range: Optional[str] = "24h"
) -> Dict[str, any]:
    """
    Retrieve alert statistics for a specific user.
    
    Args:
        user_id: The ID of the user
        time_range: Time range for statistics (default: "24h")
    
    Returns:
        Dictionary containing alert statistics
    """
    # Implementation here
    pass
```

### TypeScript (Frontend)
- Use TypeScript strict mode
- Follow Airbnb style guide
- Use functional components with hooks
- Implement proper error handling
- Use React Query for data fetching

Example:
```typescript
interface AlertFilters {
  severity?: string;
  status?: string;
  dateRange?: string;
}

export function useAlerts(
  page: number,
  perPage: number,
  filters?: AlertFilters
) {
  return useQuery({
    queryKey: ['alerts', page, perPage, filters],
    queryFn: () => fetchAlerts(page, perPage, filters),
    staleTime: 10000,
  });
}
```

## 🧪 Testing

### Before Submitting
1. **Test backend changes**
   ```bash
   cd backend
   python -m pytest tests/
   ```

2. **Test frontend changes**
   ```bash
   cd frontend/frontend
   npm run test
   npm run build  # Ensure no build errors
   ```

3. **Manual testing**
   - Start both backend and frontend
   - Test the feature thoroughly
   - Check browser console for errors
   - Verify API responses

## 📋 Pull Request Process

1. **Update documentation**
   - Update README.md if adding new features
   - Add/update API documentation in `/documentation/`
   - Include code comments

2. **Create descriptive commits**
   ```bash
   git commit -m "feat: add real-time notification filtering"
   git commit -m "fix: resolve CORS issue for SSE connections"
   git commit -m "docs: update API integration guide"
   ```

   Commit message format:
   - `feat:` New feature
   - `fix:` Bug fix
   - `docs:` Documentation changes
   - `style:` Code style changes (formatting)
   - `refactor:` Code refactoring
   - `test:` Adding/updating tests
   - `chore:` Maintenance tasks

3. **Push your changes**
   ```bash
   git push origin feature/your-feature-name
   ```

4. **Open a Pull Request**
   - Use a clear, descriptive title
   - Reference any related issues
   - Describe what changed and why
   - Include screenshots for UI changes
   - List any breaking changes

### Pull Request Template
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Backend tests pass
- [ ] Frontend builds successfully
- [ ] Manually tested feature
- [ ] Updated documentation

## Screenshots (if applicable)
Add screenshots here

## Additional Notes
Any additional information
```

## 🐛 Reporting Bugs

### Before Reporting
1. Check existing issues
2. Verify bug exists in latest version
3. Test with fresh installation

### Bug Report Template
```markdown
**Describe the bug**
Clear description of the bug

**To Reproduce**
Steps to reproduce:
1. Go to '...'
2. Click on '...'
3. See error

**Expected behavior**
What should happen

**Screenshots**
If applicable

**Environment:**
- OS: [e.g., Windows 11]
- Browser: [e.g., Chrome 120]
- Python Version: [e.g., 3.10]
- Node Version: [e.g., 18.17]

**Additional context**
Any other relevant information
```

## 💡 Feature Requests

### Feature Request Template
```markdown
**Feature Description**
Clear description of the feature

**Use Case**
Why is this feature needed?

**Proposed Solution**
How should it work?

**Alternatives Considered**
Other approaches you've thought about

**Additional Context**
Any other relevant information
```

## 🎯 Development Guidelines

### Backend Development
1. **Database Changes**
   - Create migration scripts in `/backend/scripts/`
   - Update schema documentation
   - Test with fresh database

2. **API Endpoints**
   - Add authentication where needed
   - Implement rate limiting
   - Add caching headers
   - Document in `/documentation/API_INTEGRATION.md`

3. **ML Models**
   - Document model architecture
   - Include training scripts
   - Add performance metrics
   - Version model checkpoints

### Frontend Development
1. **Components**
   - Keep components small and focused
   - Use TypeScript interfaces
   - Implement proper loading/error states
   - Add accessibility attributes

2. **State Management**
   - Use React Query for server state
   - Use React hooks for local state
   - Avoid prop drilling

3. **Performance**
   - Implement code splitting
   - Optimize bundle size
   - Use React.memo for expensive components
   - Add loading skeletons

## 📚 Documentation

### What to Document
- New features and APIs
- Configuration changes
- Breaking changes
- Migration guides
- Example usage

### Where to Document
- **README.md** - Project overview, quick start
- **/documentation/** - Detailed guides
- **Code comments** - Complex logic
- **Inline docs** - Function/class descriptions

## 🔒 Security

### Reporting Security Issues
**DO NOT** open public issues for security vulnerabilities.

Instead:
1. Email: [your-email@example.com]
2. Include detailed description
3. Steps to reproduce
4. Potential impact

### Security Best Practices
- Never commit secrets or credentials
- Use environment variables
- Validate all user input
- Implement proper authentication
- Follow OWASP guidelines

## ✅ Code Review

### As a Reviewer
- Be constructive and respectful
- Focus on code quality and maintainability
- Test the changes locally
- Check for security issues
- Verify documentation is updated

### As a Contributor
- Respond to feedback promptly
- Be open to suggestions
- Keep discussions professional
- Update PR based on feedback

## 🎓 Resources

### Project Documentation
- [Installation Guide](./documentation/INSTALLATION_CHECKLIST.md)
- [API Documentation](./documentation/API_INTEGRATION.md)
- [Quick Reference](./documentation/QUICK_REFERENCE.md)
- [Implementation Details](./documentation/IMPLEMENTATION_SUMMARY.md)

### External Resources
- [Flask Documentation](https://flask.palletsprojects.com/)
- [React Query Docs](https://tanstack.com/query/latest)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [PyTorch Documentation](https://pytorch.org/docs/)

## 🤝 Community

### Code of Conduct
- Be respectful and inclusive
- Welcome newcomers
- Provide constructive feedback
- Focus on the project goals
- Report inappropriate behavior

### Getting Help
1. Check documentation first
2. Search existing issues
3. Ask in discussions
4. Provide detailed context

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to Adaptive IDS! 🙏

Your contributions help make cybersecurity better for everyone.
