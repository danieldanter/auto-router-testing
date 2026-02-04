"""
Configuration loader for Query Router Service.
Loads secrets from the Secrets Service API.
"""
import os
import logging
import urllib.parse
import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Set to True for local testing without Secrets Service
USE_TEST_CONFIG = True


class Config:
    """Configuration manager that loads secrets from the Secrets Service."""

    def __init__(self):
        """Initialize and load configuration."""
        self.config_data = {}
        self._load_config()

    def _load_config(self):
        """Load configuration from Secrets Service or use test config."""

        # For local testing - use hardcoded test config
        if USE_TEST_CONFIG:
            logger.info("Using TEST configuration (USE_TEST_CONFIG=True)")
            self.config_data = self._get_test_config()
            return

        # Production - load from Secrets Service
        secrets_service_path = os.getenv("SECRETS_SERVICE_PATH")
        customer = os.getenv("CUSTOMER")
        api_key = os.getenv("SECRETS_SERVICE_API_KEY")

        if not all([secrets_service_path, customer, api_key]):
            logger.warning(
                "Secrets Service not configured. "
                "Set SECRETS_SERVICE_PATH, CUSTOMER, and SECRETS_SERVICE_API_KEY in .env"
            )
            return

        try:
            # Encode the customer parameter for use in the URL
            encoded_customer = urllib.parse.quote(customer)
            url = f"{secrets_service_path}/api/secretsVS?customer={encoded_customer}"
            headers = {"secrets-service-api-key": api_key}

            logger.info(f"Loading config from Secrets Service for customer: {customer}")
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            self.config_data = response.json()
            logger.info("Config loaded successfully from Secrets Service")

        except requests.RequestException as e:
            logger.error(f"Failed to load config from Secrets Service: {e}")
            self.config_data = {}

    def _get_test_config(self) -> dict:
        """
        Test configuration for local development.
        Set USE_TEST_CONFIG = False for production!
        """
        return {
            "customer": "staging",
            "vectorService": {
                # Google Vertex AI - ONLY the private key
                "googleVertexFileKey": {
                    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC0YGeLpyZknead\ngyE2t6NYkk0mMDdEBEpGZhjtD+RK9Zy6qifSeZLpBPK4e+zf1tAtgSfi+D7mDsBW\nwridDuSvvIacrrEMz3rdzyTIytbXk7M6KQdJs9dOOsohlTqGb6mMFuxgn6kQsTJP\nCbxMA4wLnPX5zFY9q3aCba4heRIiYf++e5rB18u0RaYuUzDswi0RorcSJCo4CGyq\nwyF0mCnAQwMVxTZn3eJzYSDmM1RPb2qyHLkkJSU/nnN0shWhIWSF+glO+la7ZCfM\nbZ+LF4hfevlpW1irWbkM1rmhcSC4vdQ1CIiEMjsA1ONrw4BYkH5TRzGi0aIR4QCX\nt/5T/1WrAgMBAAECggEAPjYX0HNUixRowz/EV1Zr+LLw9/BeR0/BfFlfVHgMMYxX\nw4vHU1EKCeNigZ2AW81/nIo0wxQCwZ8p2GKtgMHvvurjdKvNtdDjnBgDJFvNUKoJ\nAVDASjvEUR92srGA73gYvo/zc/ntOiwbYWZGsuLwTNsUfVTsE7YNGDwS+EmFJyUY\nbn6nMsbguNcK3HKrvqN95ChHaxrFbHE5XP80i4PqLiEsB2gJJ8pjkg79Bcuc2itd\n/mt8u48YKbKJe8v6Og/H1VOZ9qnN2KuBQMo5l9IhL91xSd77BNy1RexHpNgkmwum\nA1Cw63CZtBb6uggJJebXrQA98LC/sqTM7NHpYsjigQKBgQDZFNNeMphS4l/Iqfl7\nNZOc2ZGvGpvTEMyt1na1zFU7ll2CuuiaroZNVxaQdLn1BFkBtFEZLaZGZ0JGho1b\nYKbZtyV+Lwo4AlU7G7usF/gb2oeDbPr4X6cfP1rGA2b5saRkcUwcGNFVVqNnTNv4\n/6b8PQWHZu9PVuyUM2QEcQK3KwKBgQDUtvmnmW887tOMpWX9hzcHahiFruvnd+M1\niXJCWCfGWQTGhEGh9fN0JdDEVwhkKQAbppaAAccmAbsCUEfqidiqXCzrjHDL7rWw\nvudHfctwMF0cWdJUqn8nAQyl01RTLFAK7UPWGoHb4JUyvdQ7vlKHwdjefz3NTEql\nIGSN+S6bgQKBgQC67q8RN7pp7VwUHSKj0cAaWlSUl/JFb/sBW2QAK0PeOx6tO6yf\nvtgR84OPw6R6dFL9H7ySVPgROkwdFTLW1ET5yDe2EGXZU1D3xGr4x+80dRsqtobr\nqNruEo1lZHqhXDK298VVkJ16wk+V3d6y7dtq7FU9gwtio/S3rgVbucFf3wKBgBnp\n8KAqYRLbRYps2+/2+Q0+L56ZoMOiJ1vuUq0icDYJwjstAZHplK8hrD0/HRaWqBy2\nPr95d/l5XH77qMc549tdP1uy0EsH2bqehy5+dLpGKhG6H5WQ78ygpBnPlQZM77Nl\nFE6RDCDtSz/TQHfGx+ciBnmUpsLL+IwFVjq1kKgBAoGAN7XckuKG9ndojq9O682i\nwqXc3/EyKpuoFNoY811BMHCm/xOEUF0ezhRjHopPSSLNfWAN/2yI6QObc/Rpiz2U\n3ijp77DCl20dr59tSezKi02bezg/+fh7q52ciS/fVwFH1d/sNA/bk5OtVU3rOERG\niDrF2fbRBTpfISqPbI1OsnE=\n-----END PRIVATE KEY-----"
                }
            }
        }

    def get_google_vertex_credentials(self) -> dict:
        """
        Build Google Vertex AI credentials from Secrets Service.

        Only the private_key comes from Secrets Service.
        Other values are hardcoded (same as Vector Service).

        Returns:
            dict: Service account credentials for Vertex AI
        """
        # Get private_key from Secrets Service
        private_key = (
            self.config_data
            .get("vectorService", {})
            .get("googleVertexFileKey", {})
            .get("private_key")
        )

        if not private_key:
            logger.warning("No Google Vertex private_key found in config")
            return {}

        # Build full credentials (same structure as Vector Service)
        return {
            "type": "service_account",
            "project_id": "silicon-cocoa-428908-k8",
            "private_key_id": "vertex_key",
            "private_key": private_key,
            "client_email": "vertex-gemini-model-service@silicon-cocoa-428908-k8.iam.gserviceaccount.com",
            "client_id": "105308231232790865428",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/vertex-gemini-model-service%40silicon-cocoa-428908-k8.iam.gserviceaccount.com",
            "universe_domain": "googleapis.com"
        }

    def is_configured(self) -> bool:
        """Check if Secrets Service config was loaded successfully."""
        return bool(self.config_data)


# Singleton instance
config = Config()
