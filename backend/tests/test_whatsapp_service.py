import pytest
import os
from unittest.mock import Mock, patch
from services.whatsapp_service import WhatsAppService


class TestWhatsAppService:
    def test_init_with_credentials(self):
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': 'test_sid',
            'TWILIO_AUTH_TOKEN': 'test_token',
            'TWILIO_WHATSAPP_NUMBER': 'whatsapp:+1234567890'
        }):
            with patch('services.whatsapp_service.Client') as mock_client:
                service = WhatsAppService()
                
                assert service.account_sid == 'test_sid'
                assert service.auth_token == 'test_token'
                assert service.whatsapp_number == 'whatsapp:+1234567890'
                mock_client.assert_called_once_with('test_sid', 'test_token')

    def test_init_without_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Twilio credentials not configured"):
                WhatsAppService()

    def test_init_missing_account_sid(self):
        with patch.dict(os.environ, {
            'TWILIO_AUTH_TOKEN': 'test_token'
        }, clear=True):
            with pytest.raises(ValueError, match="Twilio credentials not configured"):
                WhatsAppService()

    def test_init_missing_auth_token(self):
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': 'test_sid'
        }, clear=True):
            with pytest.raises(ValueError, match="Twilio credentials not configured"):
                WhatsAppService()

    def test_init_default_whatsapp_number(self):
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': 'test_sid',
            'TWILIO_AUTH_TOKEN': 'test_token'
        }):
            with patch('services.whatsapp_service.Client'):
                service = WhatsAppService()
                assert service.whatsapp_number == 'whatsapp:+14155238886'

    def test_send_message_success(self):
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': 'test_sid',
            'TWILIO_AUTH_TOKEN': 'test_token'
        }):
            with patch('services.whatsapp_service.Client') as mock_client:
                mock_message = Mock()
                mock_message.sid = 'SM123'
                mock_message.status = 'sent'
                mock_message.to = 'whatsapp:+255123456789'
                mock_message.body = 'Test message'
                
                mock_client_instance = Mock()
                mock_client_instance.messages.create.return_value = mock_message
                mock_client.return_value = mock_client_instance
                
                service = WhatsAppService()
                result = service.send_message('+255123456789', 'Test message')
                
                assert result == {
                    'sid': 'SM123',
                    'status': 'sent',
                    'to': 'whatsapp:+255123456789',
                    'body': 'Test message'
                }
                
                mock_client_instance.messages.create.assert_called_once_with(
                    from_='whatsapp:+14155238886',
                    body='Test message',
                    to='whatsapp:+255123456789'
                )

    def test_send_message_twilio_error(self):
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': 'test_sid',
            'TWILIO_AUTH_TOKEN': 'test_token'
        }):
            with patch('services.whatsapp_service.Client') as mock_client:
                mock_client_instance = Mock()
                mock_client_instance.messages.create.side_effect = Exception("Twilio API error")
                mock_client.return_value = mock_client_instance
                
                service = WhatsAppService()
                
                with pytest.raises(Exception, match="Failed to send WhatsApp message: Twilio API error"):
                    service.send_message('+255123456789', 'Test message')

    def test_send_welcome_message_english(self):
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': 'test_sid',
            'TWILIO_AUTH_TOKEN': 'test_token'
        }):
            with patch('services.whatsapp_service.Client'):
                service = WhatsAppService()
                
                with patch.object(service, 'send_message') as mock_send:
                    mock_send.return_value = {'sid': 'SM123', 'status': 'sent'}
                    
                    result = service.send_welcome_message('+255123456789', 'en')
                    
                    expected_message = "Welcome to AgriConnect! We're here to help you with agricultural information and support. How can we assist you today?"
                    mock_send.assert_called_once_with('+255123456789', expected_message)
                    assert result == {'sid': 'SM123', 'status': 'sent'}

    def test_send_welcome_message_swahili(self):
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': 'test_sid',
            'TWILIO_AUTH_TOKEN': 'test_token'
        }):
            with patch('services.whatsapp_service.Client'):
                service = WhatsAppService()
                
                with patch.object(service, 'send_message') as mock_send:
                    mock_send.return_value = {'sid': 'SM456', 'status': 'sent'}
                    
                    result = service.send_welcome_message('+255123456789', 'sw')
                    
                    expected_message = "Karibu AgriConnect! Tuko hapa kukusaidia na maelezo na msaada wa kilimo. Tunawezaje kukusaidia leo?"
                    mock_send.assert_called_once_with('+255123456789', expected_message)
                    assert result == {'sid': 'SM456', 'status': 'sent'}

    def test_send_welcome_message_unknown_language(self):
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': 'test_sid',
            'TWILIO_AUTH_TOKEN': 'test_token'
        }):
            with patch('services.whatsapp_service.Client'):
                service = WhatsAppService()
                
                with patch.object(service, 'send_message') as mock_send:
                    mock_send.return_value = {'sid': 'SM789', 'status': 'sent'}
                    
                    result = service.send_welcome_message('+255123456789', 'fr')
                    
                    # Should default to English
                    expected_message = "Welcome to AgriConnect! We're here to help you with agricultural information and support. How can we assist you today?"
                    mock_send.assert_called_once_with('+255123456789', expected_message)

    def test_send_welcome_message_no_language(self):
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': 'test_sid',
            'TWILIO_AUTH_TOKEN': 'test_token'
        }):
            with patch('services.whatsapp_service.Client'):
                service = WhatsAppService()
                
                with patch.object(service, 'send_message') as mock_send:
                    mock_send.return_value = {'sid': 'SM999', 'status': 'sent'}
                    
                    result = service.send_welcome_message('+255123456789')
                    
                    # Should default to English
                    expected_message = "Welcome to AgriConnect! We're here to help you with agricultural information and support. How can we assist you today?"
                    mock_send.assert_called_once_with('+255123456789', expected_message)

    def test_send_message_custom_whatsapp_number(self):
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': 'test_sid',
            'TWILIO_AUTH_TOKEN': 'test_token',
            'TWILIO_WHATSAPP_NUMBER': 'whatsapp:+1987654321'
        }):
            with patch('services.whatsapp_service.Client') as mock_client:
                mock_message = Mock()
                mock_message.sid = 'SM123'
                mock_message.status = 'sent'
                mock_message.to = 'whatsapp:+255123456789'
                mock_message.body = 'Test message'
                
                mock_client_instance = Mock()
                mock_client_instance.messages.create.return_value = mock_message
                mock_client.return_value = mock_client_instance
                
                service = WhatsAppService()
                service.send_message('+255123456789', 'Test message')
                
                mock_client_instance.messages.create.assert_called_once_with(
                    from_='whatsapp:+1987654321',  # Custom number used
                    body='Test message',
                    to='whatsapp:+255123456789'
                )