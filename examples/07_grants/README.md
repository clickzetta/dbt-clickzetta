# 07 权限管理（Grants）

通过 `grants` 配置，dbt 在每次运行后自动执行 GRANT/REVOKE，无需手动管理权限。

## 运行

```bash
dbt run
```

## 说明

- 授权给**角色**：直接写角色名，如 `workspace_analyst`
- 授权给**用户**：加 `user:` 前缀，如 `user:alice`
- 支持多个 grantee：`['workspace_analyst', 'user:alice']`
- grants 变更后重新运行，dbt 会自动 REVOKE 旧权限、GRANT 新权限
- 支持的权限类型：`select`、`insert`、`alter`、`drop` 等（与 ClickZetta 权限点一致）
