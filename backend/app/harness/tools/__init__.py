"""Tool Harness — tool là một hợp đồng API giữa model và code.

- registry.py  @agent_tool(risk=...): schema sinh từ type hint + docstring (pydantic),
               ToolRegistry riêng cho từng agent (least privilege)                    (bước 3)
- executor.py  tra tool → kiểm tra rủi ro → validate tham số → chạy có timeout
               → rút gọn output → trace                                              (bước 3; bước 11: policy)
Mức rủi ro: read | write | destructive | external.
"""
