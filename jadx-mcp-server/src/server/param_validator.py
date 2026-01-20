"""
Parameter Validator - 参数验证
验证 Transfer API 的输入参数
"""

import re
from typing import List
from src.server.logging_config import get_logger

logger = get_logger("param_validator")

# 合法的 Java 类名格式：字母、数字、点、美元符、下划线
CLASS_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9.$_]+$')

# 限制常量
MAX_CLASS_NAME_LENGTH = 512
MAX_CLASSES_PER_REQUEST = 100


class ValidationError(Exception):
    """参数验证错误"""
    pass


def validate_class_names(classes_param: str) -> List[str]:
    """
    验证类名参数
    
    Args:
        classes_param: 逗号分隔的类名字符串
    
    Returns:
        验证通过的类名列表
    
    Raises:
        ValidationError: 验证失败
    """
    if not classes_param or not classes_param.strip():
        raise ValidationError("Empty classes parameter")
    
    # 分割并清理
    class_names = [c.strip() for c in classes_param.split(",") if c.strip()]
    
    if not class_names:
        raise ValidationError("No valid class names provided")
    
    # 数量限制
    if len(class_names) > MAX_CLASSES_PER_REQUEST:
        logger.warning(f"Too many classes requested: {len(class_names)}")
        raise ValidationError(
            f"Too many classes. Maximum {MAX_CLASSES_PER_REQUEST} per request, got {len(class_names)}"
        )
    
    # 验证每个类名
    for name in class_names:
        # 长度限制
        if len(name) > MAX_CLASS_NAME_LENGTH:
            logger.warning(f"Class name too long: {name[:50]}...")
            raise ValidationError(
                f"Class name too long (max {MAX_CLASS_NAME_LENGTH} chars): {name[:50]}..."
            )
        
        # 格式验证
        if not CLASS_NAME_PATTERN.match(name):
            logger.warning(f"Invalid class name format: {name}")
            raise ValidationError(
                f"Invalid class name format. Only alphanumeric, dots, dollar signs, "
                f"and underscores allowed: {name}"
            )
    
    logger.debug(f"Validated {len(class_names)} class names")
    return class_names


def validate_token(token: str) -> str:
    """
    验证令牌格式
    
    Args:
        token: 令牌字符串
    
    Returns:
        清理后的令牌
    
    Raises:
        ValidationError: 验证失败
    """
    if not token or not token.strip():
        raise ValidationError("Empty token")
    
    token = token.strip()
    
    # 令牌长度检查（应该是 32 字符，但允许一定容差）
    if len(token) < 20 or len(token) > 64:
        logger.warning(f"Invalid token length: {len(token)}")
        raise ValidationError("Invalid token format")
    
    # 令牌字符检查（应该是 URL 安全的 Base64）
    if not re.match(r'^[A-Za-z0-9_-]+$', token):
        logger.warning("Invalid token characters")
        raise ValidationError("Invalid token format")
    
    return token


def validate_format(format_param: str) -> str:
    """
    验证格式参数
    
    Args:
        format_param: 格式字符串 (json/zip)
    
    Returns:
        验证后的格式
    
    Raises:
        ValidationError: 验证失败
    """
    if not format_param:
        return "json"  # 默认
    
    format_lower = format_param.lower().strip()
    
    if format_lower not in ["json", "zip"]:
        raise ValidationError(f"Invalid format. Must be 'json' or 'zip', got '{format_param}'")
    
    return format_lower


def validate_compression(compression_param: str) -> str:
    """
    验证压缩参数
    
    Args:
        compression_param: 压缩算法 (br/gzip/none/auto)
    
    Returns:
        验证后的压缩算法
    
    Raises:
        ValidationError: 验证失败
    """
    if not compression_param:
        return "auto"  # 默认
    
    compression_lower = compression_param.lower().strip()
    
    valid_options = ["br", "gzip", "none", "auto"]
    if compression_lower not in valid_options:
        raise ValidationError(
            f"Invalid compression. Must be one of {valid_options}, got '{compression_param}'"
        )
    
    return compression_lower
