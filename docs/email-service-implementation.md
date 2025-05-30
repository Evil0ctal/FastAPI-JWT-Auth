# Email Service Implementation

## Overview

A comprehensive email service has been implemented for the FastAPI JWT Auth Template, supporting transactional emails like verification, password reset, and welcome messages.

## Features

### Email Service (`app/services/email.py`)
- **SMTP Support**: Configurable SMTP settings for any email provider
- **TLS/SSL Support**: Secure email transmission
- **Template System**: Jinja2-based HTML email templates
- **Async Support**: Non-blocking email sending
- **Fallback Text**: Plain text alternatives for all HTML emails

### Email Templates
Located in `app/templates/emails/`:
- `base.html`: Base template with consistent styling
- `verification.html`: Email verification template
- `password_reset.html`: Password reset template  
- `welcome.html`: Welcome email template

### Email Verification System (`app/services/email_verification.py`)
- **Token Generation**: Secure random tokens for verification
- **Expiry Management**: 24-hour expiration for verification links
- **Database Tracking**: Verification status stored in database
- **Resend Support**: Users can request new verification emails

## Configuration

Add to your `.env` file:

```env
# Email Settings
EMAIL_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=noreply@yourapp.com
SMTP_TLS=true
SMTP_SSL=false
FRONTEND_URL=http://localhost:8000
```

### Gmail Setup
1. Enable 2-factor authentication
2. Generate an app-specific password
3. Use the app password as SMTP_PASSWORD

### Other Providers
- **SendGrid**: Use `smtp.sendgrid.net` with API key
- **AWS SES**: Use SES SMTP endpoint with IAM credentials
- **Mailgun**: Use Mailgun SMTP settings

## API Endpoints

### Email Verification
```
POST /api/v1/auth/verify-email?token={token}
```

### Resend Verification
```
POST /api/v1/auth/resend-verification
{
  "email": "user@example.com"
}
```

## Usage Flow

1. **User Registration**
   - User registers with email
   - Verification email sent automatically
   - User marked as unverified

2. **Email Verification**
   - User clicks verification link
   - Token validated
   - User marked as verified

3. **Resend Verification**
   - User can request new verification email
   - Old tokens invalidated
   - New 24-hour token generated

## Demo Mode

When `EMAIL_ENABLED=false`:
- Emails are not sent
- Verification tokens printed to console
- Useful for development/testing

## Security Features

- Tokens expire after 24 hours
- One-time use tokens
- Secure random token generation
- Email content sanitization

## Testing

Test email functionality:
```bash
# Register new user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","username":"testuser","password":"testpass123"}'

# Check console for verification token if EMAIL_ENABLED=false
# Or check email if EMAIL_ENABLED=true

# Verify email
curl -X POST "http://localhost:8000/api/v1/auth/verify-email?token=YOUR_TOKEN"

# Resend verification
curl -X POST http://localhost:8000/api/v1/auth/resend-verification \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com"}'
```

## Next Steps

- Implement password reset functionality
- Add email notification preferences
- Create email queue for high volume
- Add email analytics tracking