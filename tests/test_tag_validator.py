import pytest
from wafr_genai_accelerator.tag_validator import TagValidator

def test_empty_value():
    invalid_tags = {
        'Environment': 'prod',
        'Project': '',  # Empty value
        'Owner': 'test'
    }
    with pytest.raises(ValueError) as exc_info:
        TagValidator.validate_tags(invalid_tags)
    assert 'cannot be empty' in str(exc_info.value)