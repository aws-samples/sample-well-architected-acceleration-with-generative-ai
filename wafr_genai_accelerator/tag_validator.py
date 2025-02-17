from typing import Dict

class TagValidator:
    """Validator for AWS resource tags."""
    
    MAX_TAG_LENGTH = 256
    MAX_VALUE_LENGTH = 256
    
    @classmethod
    def validate_tags(cls, tags: Dict[str, str]) -> Dict[str, str]:
        """
        Validates and standardizes the provided tags.
        
        Args:
            tags: Dictionary of tags to validate
            
        Returns:
            Dictionary of validated and standardized tags
            
        Raises:
            ValueError: If tags are invalid
        """

        validated_tags = {}
        for key, value in tags.items():
            # Validate key length
            if len(key) > cls.MAX_TAG_LENGTH:
                raise ValueError(f"Tag key '{key}' exceeds maximum length of {cls.MAX_TAG_LENGTH}")
            
            # Validate value length
            if len(value) > cls.MAX_VALUE_LENGTH:
                raise ValueError(f"Value for tag '{key}' exceeds maximum length of {cls.MAX_VALUE_LENGTH}")
            
            # Validate value is not empty
            if not value:
                raise ValueError(f"Value for tag '{key}' cannot be empty")
            
            validated_tags[key] = value
            
        return validated_tags