"""
JADX MCP Server - Frida Hook Generation Tools

此模块提供自动生成 Frida hook 脚本的 MCP 工具，支持：
  - 单方法 / 构造方法 / 全部方法的 hook 脚本
  - 类级别追踪脚本（可选包含子类）
  - 枚举类实例、静态方法、字段的枚举脚本

Author: JADX AI MCP
License: See LICENSE file
"""

from typing import Optional
from src.server.logging_config import get_logger
from src.server.request_context import get_from_jadx_for_current_user as get_from_jadx

logger = get_logger("frida_tools")


async def generate_frida_hook(
    class_name: str,
    method_name: Optional[str] = None,
    hook_type: str = "both",
    instance_id: Optional[str] = None,
) -> dict:
    """
    为指定类/方法生成可直接运行的 Frida hook 脚本。

    支持重载方法（自动为每个重载版本生成 .overload() 调用）。
    使用 FridaTypeConverter 保证参数类型字符串格式正确。

    Args:
        class_name: 完全限定类名（如 com.example.MainActivity）
        method_name: 方法名（可选）。缺省时 hook_type 自动升级为 all_methods。
        hook_type: hook 类型，可选值：
            - method_enter  — 仅在方法入口打印参数
            - method_exit   — 仅在方法返回时打印返回值
            - both          — 入口 + 返回值（默认）
            - constructor   — 钩住所有构造方法
            - all_methods   — 钩住类中所有方法
        instance_id: 可选，目标 JADX 实例名称。

    Returns:
        dict:
            - class_name: 目标类名
            - method_name: 目标方法名（或 "(all)"）
            - hook_type: 使用的 hook 类型
            - script: 生成的 Frida JavaScript 脚本

    MCP Tool: generate_frida_hook
    Description: 自动生成可直接运行的 Frida hook 脚本，支持重载方法和正确类型转换
    """
    params: dict = {"class_name": class_name, "hook_type": hook_type}
    if method_name:
        params["method_name"] = method_name

    result = await get_from_jadx("generate-frida-hook", params, instance_id=instance_id)
    if "error" in result:
        logger.warning(f"generate_frida_hook error: {result.get('error')}")
    else:
        logger.info(f"generate_frida_hook: class={class_name}, method={method_name}, type={hook_type}")
    return result


async def generate_frida_trace(
    class_name: str,
    include_subclasses: bool = False,
    instance_id: Optional[str] = None,
) -> dict:
    """
    生成追踪指定类所有方法调用的 Frida 脚本。

    每个方法调用都会打印入口参数和返回值，并附加时间戳标签，
    便于在 frida-trace / frida CLI 中快速定位调用链。

    Args:
        class_name: 完全限定类名（如 com.example.NetworkManager）
        include_subclasses: 是否同时追踪同包内的直接子类，默认 False。
        instance_id: 可选，目标 JADX 实例名称。

    Returns:
        dict:
            - class_name: 目标类名
            - include_subclasses: 是否包含子类
            - script: 生成的 Frida JavaScript 追踪脚本

    MCP Tool: generate_frida_trace
    Description: 生成类级别的 Frida 追踪脚本，记录所有方法调用的入参和返回值
    """
    params: dict = {
        "class_name": class_name,
        "include_subclasses": "true" if include_subclasses else "false",
    }

    result = await get_from_jadx("generate-frida-trace", params, instance_id=instance_id)
    if "error" in result:
        logger.warning(f"generate_frida_trace error: {result.get('error')}")
    else:
        logger.info(f"generate_frida_trace: class={class_name}, subclasses={include_subclasses}")
    return result


async def generate_frida_enum(
    class_name: str,
    instance_id: Optional[str] = None,
) -> dict:
    """
    生成枚举类实例、调用静态方法、读取字段的 Frida 脚本。

    生成内容：
    1. 读取所有 static 字段值
    2. 调用无参 static 方法并打印结果
    3. 对 enum 类调用 values() 枚举所有常量
    4. 用 Java.choose() 枚举内存中的活跃实例并读取实例字段

    Args:
        class_name: 完全限定类名（如 com.example.Config）
        instance_id: 可选，目标 JADX 实例名称。

    Returns:
        dict:
            - class_name: 目标类名
            - script: 生成的 Frida JavaScript 枚举脚本

    MCP Tool: generate_frida_enum
    Description: 生成枚举类实例和静态成员的 Frida 脚本，适用于提取运行时配置和常量
    """
    params: dict = {"class_name": class_name}

    result = await get_from_jadx("generate-frida-enum", params, instance_id=instance_id)
    if "error" in result:
        logger.warning(f"generate_frida_enum error: {result.get('error')}")
    else:
        logger.info(f"generate_frida_enum: class={class_name}")
    return result


# 保存模块级函数引用，防止被 register_frida_tools 内部同名函数遮蔽
_generate_frida_hook = generate_frida_hook
_generate_frida_trace = generate_frida_trace
_generate_frida_enum = generate_frida_enum


def register_frida_tools(mcp, with_busy_check):
    """将 Frida 脚本生成工具注册到 MCP Server"""

    @mcp.tool()
    @with_busy_check
    async def generate_frida_hook(
        class_name: str,
        method_name: Optional[str] = None,
        hook_type: str = "both",
        instance_id: Optional[str] = None,
    ) -> dict:
        """生成可直接运行的 Frida hook 脚本，支持重载方法和正确类型转换。

        hook_type 可选值：
          - method_enter  — 仅记录入口参数
          - method_exit   — 仅记录返回值
          - both          — 入口 + 返回值（默认）
          - constructor   — 钩住所有构造方法
          - all_methods   — 钩住类中所有方法

        Args:
            class_name: 完全限定类名（如 'com.example.MainActivity'）
            method_name: 方法名，缺省时自动使用 all_methods 模式
            hook_type: hook 类型（见上方说明），默认 'both'
            instance_id: 可选，目标 JADX 实例名称
        """
        return await _generate_frida_hook(
            class_name,
            method_name=method_name,
            hook_type=hook_type,
            instance_id=instance_id,
        )

    @mcp.tool()
    @with_busy_check
    async def generate_frida_trace(
        class_name: str,
        include_subclasses: bool = False,
        instance_id: Optional[str] = None,
    ) -> dict:
        """生成类级别的 Frida 追踪脚本，记录所有方法调用的入参和返回值。

        Args:
            class_name: 完全限定类名（如 'com.example.NetworkManager'）
            include_subclasses: 是否同时追踪直接子类，默认 False
            instance_id: 可选，目标 JADX 实例名称
        """
        return await _generate_frida_trace(
            class_name,
            include_subclasses=include_subclasses,
            instance_id=instance_id,
        )

    @mcp.tool()
    @with_busy_check
    async def generate_frida_enum(
        class_name: str,
        instance_id: Optional[str] = None,
    ) -> dict:
        """生成枚举类实例和静态成员的 Frida 脚本，适用于提取运行时配置和常量。

        生成内容：静态字段读取、静态方法调用、enum values()、Java.choose() 实例枚举。

        Args:
            class_name: 完全限定类名（如 'com.example.Config'）
            instance_id: 可选，目标 JADX 实例名称
        """
        return await _generate_frida_enum(class_name, instance_id=instance_id)
