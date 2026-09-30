import gzip
import io
import socket
import unittest
from unittest.mock import Mock, patch
from urllib.request import Request
from PIL import Image
from choroy_reader import network, core
from choroy_reader.safe_images import open_image


class SourceSecurityTests(unittest.TestCase):
    def test_rejects_non_web_and_credential_urls(self):
        for url in ('file:///etc/passwd', 'ftp://example.com/a', 'data:text/plain,abc',
                    'javascript:alert(1)', 'https://user:secret@example.com',
                    'https://example.com/\nheader', 'https:///missing'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                network.download(url)

    def test_blocks_private_dns_results_before_connecting(self):
        for host in ('127.0.0.1', '192.168.1.1', '169.254.169.254', '0.0.0.0',
                     '::1', '::ffff:127.0.0.1', '224.0.0.1', 'ff02::1'):
            addresses = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (host, 80))]
            with patch.object(socket, 'getaddrinfo', return_value=addresses), patch.object(socket, 'socket') as connect:
                with self.assertRaises(ValueError):
                    network.public_connection(('malicious.example', 80))
                connect.assert_not_called()

    def test_connects_to_validated_address_without_second_resolution(self):
        addresses = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.215.14', 443))]
        with patch.object(socket, 'getaddrinfo', return_value=addresses) as resolve, patch.object(socket, 'socket') as factory:
            network.public_connection(('example.com', 443), timeout=5)
            resolve.assert_called_once()
            factory.return_value.connect.assert_called_once_with(('93.184.215.14', 443))

    def test_redirect_cannot_downgrade_tls_or_use_other_protocols(self):
        for url in ('http://example.com', 'ftp://example.com', 'file:///etc/passwd'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                network.SafeRedirect().redirect_request(Request('https://example.com'), None, 302, '', {}, url)

    def test_limits_compressed_and_uncompressed_responses(self):
        for data, headers in ((b'x' * 101, {}), (gzip.compress(b'x' * 101), {'Content-Encoding': 'gzip'})):
            response = Mock()
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            response.read.side_effect = io.BytesIO(data).read
            response.info.return_value = headers
            with patch.object(network, 'MAX_DOWNLOAD', 100), patch.object(network.urllib.request, 'build_opener') as opener:
                opener.return_value.open.return_value = response
                with self.assertRaises(ValueError):
                    network.download('https://example.com')

    def test_images_reject_active_formats_and_excessive_dimensions(self):
        for data in (b'<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>', b'%!PS-Adobe-3.0 EPSF-3.0'):
            with self.assertRaises(OSError):
                open_image(data)
        output = io.BytesIO()
        Image.new('RGB', (20, 20)).save(output, 'PNG')
        with patch('choroy_reader.safe_images.MAX_PIXELS', 100), self.assertRaises(ValueError):
            open_image(output.getvalue())

    def test_article_scripts_are_removed(self):
        markup = '<article><script>bad()</script><style>bad{}</style><p>Texto seguro</p></article>'
        self.assertEqual(core.article_text(markup), 'Texto seguro')
