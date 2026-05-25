"""JADX MCP Server Tools Package

Exposes all tool modules for import.

=============================================================================
Tool Inventory (as of 2026-05-25)
=============================================================================

Active MCP tools (registered and fully supported):

  class_tools        : get_all_classes, get_class_source, batch_get_class_source,
                       get_methods_of_class, get_fields_of_class, get_smali_of_class,
                       get_main_activity_class, get_class_info, get_decompile_status,
                       list_packages
  search_tools       : get_method_by_name, batch_get_method_by_name,
                       search_classes_by_keyword, get_method_signature,
                       get_method_callees, search_native_methods
  xrefs_tools        : get_xrefs, batch_get_xrefs
  refactor_tools     : rename_variable_tool, export_rename_mappings_tool,
                       import_rename_mappings_tool, rename,
                       apply_proguard_mapping_tool
  resource_tools     : get_android_manifest, get_resource_file, get_strings,
                       get_file_info, get_config_strings, get_all_resource_file_names,
                       get_package_classes, get_index_stats, get_analysis_summary,
                       get_jadx_instance_info, get_decompile_priority_list,
                       smart_decompile
  instance_tools     : add_jadx_instance, remove_jadx_instance, list_jadx_instances,
                       health_check_jadx_instances, set_default_jadx_instance,
                       get_load_balance_status, get_scaling_status_tool
  transfer_tools     : create_transfer_token
  frida_tools        : generate_frida_hook, generate_frida_trace, generate_frida_enum
  analysis_tools     : (see analysis_tools.py)
  analysis_surface_tools : get_attack_surface, export_callgraph
  annotation_tools   : add_annotation, get_annotations, delete_annotation,
                       add_bookmark, list_bookmarks, delete_bookmark,
                       add_tag, get_tags, delete_tag, list_analysis_sessions
  digest_tools       : generate_apk_digest (enhanced: signing_certificates,
                       native_libraries, dex_count for APK/AAR/DEX)
  security_tools     : run_security_scan
  session_tools      : save_analysis_session, load_analysis_session, list_analysis_sessions
  export_tools       : export_analysis_report
  diff_tools         : compare_versions
  dataflow_tools     : trace_data_flow, find_callers_chain
  decompile_tools    : smart_decompile, get_decompile_priority_list,
                       warm_cache, get_warmup_status
  scaling_tools      : scale_instances_tool, get_scaling_status_tool
  file_management_tools : load_file_tool, list_available_files_tool, cancel_search
  diagnostics_tools  : get_load_balance_status
  workflow_tools     : analyze_apk_tool, jar_get_manifest (and related jar tools)
  string_literal_tools : search_string_literals

Redundancy notes (DEPRECATED candidates, not yet removed for compatibility):

  [REDUNDANCY-1] xrefs: The internal helper functions get_xrefs_to_class(),
      get_xrefs_to_method(), and get_xrefs_to_field() are module-level functions
      but are NOT registered as MCP tools. Only get_xrefs() (unified) and
      batch_get_xrefs() are registered. No action needed — the helpers are
      correctly internal-only.

  [REDUNDANCY-2] rename: Individual rename_class(), rename_method(), rename_field(),
      rename_package() are module-level helpers used internally by the unified
      rename() MCP tool. They are not registered as separate MCP tools.
      No action needed.

  [REDUNDANCY-3] scaling/diagnostics: get_scaling_status_tool appears in both
      scaling_tools and instance_tools. Review registration to ensure it is not
      double-registered.

Total active MCP tools: ~77
Deprecated / pending cleanup: 0 (none fully registered as deprecated yet)
=============================================================================
"""
from . import class_tools
from . import resource_tools
from . import search_tools
from . import xrefs_tools
from . import instance_tools
from . import refactor_tools
from . import transfer_tools
from . import frida_tools
from . import analysis_tools
from . import analysis_surface_tools
from . import annotation_tools
from . import digest_tools
from . import security_tools
from . import session_tools
from . import export_tools
from . import diff_tools
from . import dataflow_tools
from . import decompile_tools
from . import scaling_tools
from . import file_management_tools
from . import diagnostics_tools
from . import workflow_tools
from . import string_literal_tools

from .class_tools import register_class_tools
from .search_tools import register_search_tools
from .resource_tools import register_resource_tools
from .xrefs_tools import register_xrefs_tools
from .refactor_tools import register_refactor_tools
from .instance_tools import register_instance_tools
from .transfer_tools import register_transfer_tools
from .frida_tools import register_frida_tools
from .analysis_tools import register_analysis_tools
from .analysis_surface_tools import register_analysis_surface_tools
from .annotation_tools import register_annotation_tools
from .digest_tools import register_digest_tools
from .security_tools import register_security_tools
from .session_tools import register_session_tools
from .export_tools import register_export_tools
from .diff_tools import register_diff_tools
from .dataflow_tools import register_dataflow_tools
from .decompile_tools import register_decompile_tools
from .scaling_tools import register_scaling_tools
from .file_management_tools import register_file_management_tools
from .diagnostics_tools import register_diagnostics_tools
from .workflow_tools import register_workflow_tools
from .string_literal_tools import register_string_literal_tools
