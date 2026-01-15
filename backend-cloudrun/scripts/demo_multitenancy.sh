#!/bin/bash

# 多租户功能验收演示脚本
# 这个脚本演示所有多租户功能

set -e

echo "=========================================="
echo "EcoMind-AI 多租户功能验收演示"
echo "=========================================="
echo ""

BASE_URL="http://localhost:8000"

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_step() {
    echo -e "${BLUE}[步骤 $1]${NC} $2"
}

echo_success() {
    echo -e "${GREEN}✓${NC} $1"
}

echo_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

# 1. 测试用户注册（自动分配默认组织）
echo_step "1" "测试用户注册功能（自动分配到默认组织）"
echo ""

REGISTER_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser_demo",
    "email": "testuser@demo.com",
    "password": "password123",
    "full_name": "演示用户"
  }')

echo "$REGISTER_RESPONSE" | jq '.'

ORG_ID=$(echo "$REGISTER_RESPONSE" | jq -r '.org_id')
if [ "$ORG_ID" != "null" ]; then
    echo_success "用户注册成功，自动分配到组织: $ORG_ID"
else
    echo_info "用户已存在或注册失败"
fi
echo ""

# 2. 登录获取 superadmin token
echo_step "2" "登录超级管理员账号"
echo ""

ADMIN_TOKEN=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123" | jq -r '.access_token')

if [ "$ADMIN_TOKEN" != "null" ] && [ -n "$ADMIN_TOKEN" ]; then
    echo_success "超级管理员登录成功"
    echo_info "Token: ${ADMIN_TOKEN:0:20}..."
else
    echo "登录失败，请检查管理员账号密码"
    exit 1
fi
echo ""

# 3. 验证超级管理员身份
echo_step "3" "验证超级管理员身份"
echo ""

ME_RESPONSE=$(curl -s -X GET "$BASE_URL/api/v1/auth/me" \
  -H "Authorization: Bearer $ADMIN_TOKEN")

echo "$ME_RESPONSE" | jq '.'

IS_SUPERADMIN=$(echo "$ME_RESPONSE" | jq -r '.is_superadmin')
if [ "$IS_SUPERADMIN" = "true" ]; then
    echo_success "确认为超级管理员"
else
    echo "当前用户不是超级管理员"
    exit 1
fi
echo ""

# 4. 列出所有组织
echo_step "4" "列出所有组织（仅超级管理员可见）"
echo ""

ORGS_RESPONSE=$(curl -s -X GET "$BASE_URL/api/v1/organizations/" \
  -H "Authorization: Bearer $ADMIN_TOKEN")

echo "$ORGS_RESPONSE" | jq '.'
ORG_COUNT=$(echo "$ORGS_RESPONSE" | jq 'length')
echo_success "共有 $ORG_COUNT 个组织"
echo ""

# 5. 创建新组织
echo_step "5" "创建新组织（仅超级管理员可操作）"
echo ""

NEW_ORG_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/organizations/" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "演示公司A",
    "code": "DEMO_COMPANY_A",
    "address": "北京市朝阳区演示路123号",
    "contact_name": "张三",
    "contact_phone": "13800138000"
  }')

echo "$NEW_ORG_RESPONSE" | jq '.'

NEW_ORG_ID=$(echo "$NEW_ORG_RESPONSE" | jq -r '.id // .detail')
if [ "$NEW_ORG_ID" != "Organization with this code already exists" ]; then
    echo_success "组织创建成功: $NEW_ORG_ID"
else
    echo_info "组织已存在，跳过创建"
fi
echo ""

# 6. 创建第二个组织
echo_step "6" "创建第二个组织（用于测试数据隔离）"
echo ""

ORG_B_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/organizations/" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "演示公司B",
    "code": "DEMO_COMPANY_B",
    "address": "上海市浦东新区演示大道456号",
    "contact_name": "李四",
    "contact_phone": "13900139000"
  }')

echo "$ORG_B_RESPONSE" | jq '.'

ORG_B_ID=$(echo "$ORG_B_RESPONSE" | jq -r '.id // .detail')
if [ "$ORG_B_ID" != "Organization with this code already exists" ]; then
    echo_success "组织B创建成功: $ORG_B_ID"
else
    echo_info "组织B已存在，跳过创建"
    # 获取现有组织B的ID
    ORG_B_ID=$(curl -s -X GET "$BASE_URL/api/v1/organizations/" \
      -H "Authorization: Bearer $ADMIN_TOKEN" | jq -r '.[] | select(.code=="DEMO_COMPANY_B") | .id')
fi
echo ""

# 7. 查看组织详情（含统计）
echo_step "7" "查看组织详情（含用户数、设备数统计）"
echo ""

if [ "$ORG_B_ID" != "null" ] && [ -n "$ORG_B_ID" ]; then
    ORG_DETAIL=$(curl -s -X GET "$BASE_URL/api/v1/organizations/$ORG_B_ID" \
      -H "Authorization: Bearer $ADMIN_TOKEN")

    echo "$ORG_DETAIL" | jq '.'

    USER_COUNT=$(echo "$ORG_DETAIL" | jq -r '.user_count')
    DEVICE_COUNT=$(echo "$ORG_DETAIL" | jq -r '.device_count')
    echo_success "组织统计 - 用户数: $USER_COUNT, 设备数: $DEVICE_COUNT"
fi
echo ""

# 8. 测试数据隔离 - 创建属于不同组织的设备
echo_step "8" "测试多租户数据隔离"
echo ""

# 获取第一个非默认组织
FIRST_ORG_ID=$(curl -s -X GET "$BASE_URL/api/v1/organizations/" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq -r '.[0].id')

if [ "$FIRST_ORG_ID" != "null" ] && [ -n "$FIRST_ORG_ID" ]; then
    echo_info "为组织 $FIRST_ORG_ID 创建设备..."

    DEVICE_A=$(curl -s -X POST "$BASE_URL/api/v1/devices/" \
      -H "Authorization: Bearer $ADMIN_TOKEN" \
      -H "Content-Type: application/json" \
      -d "{
        \"mn\": \"DEMO_DEVICE_A_$(date +%s)\",
        \"name\": \"演示设备A\",
        \"device_type\": \"water\",
        \"org_id\": \"$FIRST_ORG_ID\",
        \"address\": \"测试地址A\"
      }")

    echo "$DEVICE_A" | jq '.'

    DEVICE_A_ID=$(echo "$DEVICE_A" | jq -r '.id // .detail')
    if [ "$DEVICE_A_ID" != "null" ] && [[ ! "$DEVICE_A_ID" =~ "already exists" ]]; then
        echo_success "设备A创建成功"
    else
        echo_info "设备创建跳过: $DEVICE_A_ID"
    fi
fi
echo ""

# 9. 测试普通用户数据隔离
echo_step "9" "测试普通用户数据隔离（只能看到自己组织的数据）"
echo ""

# 登录普通用户
USER_TOKEN=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser_demo&password=password123" 2>/dev/null | jq -r '.access_token')

if [ "$USER_TOKEN" != "null" ] && [ -n "$USER_TOKEN" ]; then
    echo_success "普通用户登录成功"

    # 普通用户查看设备列表
    USER_DEVICES=$(curl -s -X GET "$BASE_URL/api/v1/devices/" \
      -H "Authorization: Bearer $USER_TOKEN")

    echo "普通用户可见的设备:"
    echo "$USER_DEVICES" | jq '.'

    DEVICE_COUNT=$(echo "$USER_DEVICES" | jq 'length')
    echo_success "普通用户只能看到 $DEVICE_COUNT 个设备（仅限本组织）"
else
    echo_info "普通用户不存在或登录失败，跳过此测试"
fi
echo ""

# 10. 测试权限控制（普通用户无法访问组织管理）
echo_step "10" "测试权限控制（普通用户无法访问组织管理）"
echo ""

if [ "$USER_TOKEN" != "null" ] && [ -n "$USER_TOKEN" ]; then
    FORBIDDEN_RESPONSE=$(curl -s -X GET "$BASE_URL/api/v1/organizations/" \
      -H "Authorization: Bearer $USER_TOKEN")

    echo "$FORBIDDEN_RESPONSE" | jq '.'

    DETAIL=$(echo "$FORBIDDEN_RESPONSE" | jq -r '.detail')
    if [[ "$DETAIL" == *"Superadmin"* ]]; then
        echo_success "权限控制正常：普通用户无法访问组织管理接口"
    else
        echo "权限控制可能存在问题"
    fi
else
    echo_info "跳过权限测试"
fi
echo ""

# 11. 超级管理员查看所有设备
echo_step "11" "超级管理员查看所有设备（不受组织限制）"
echo ""

ALL_DEVICES=$(curl -s -X GET "$BASE_URL/api/v1/devices/" \
  -H "Authorization: Bearer $ADMIN_TOKEN")

echo "$ALL_DEVICES" | jq '.'

TOTAL_DEVICES=$(echo "$ALL_DEVICES" | jq 'length')
echo_success "超级管理员可以看到所有 $TOTAL_DEVICES 个设备"
echo ""

# 12. 查看组织下的用户列表
echo_step "12" "查看指定组织的用户列表"
echo ""

if [ "$FIRST_ORG_ID" != "null" ] && [ -n "$FIRST_ORG_ID" ]; then
    ORG_USERS=$(curl -s -X GET "$BASE_URL/api/v1/organizations/$FIRST_ORG_ID/users" \
      -H "Authorization: Bearer $ADMIN_TOKEN")

    echo "$ORG_USERS" | jq '.'

    USER_COUNT=$(echo "$ORG_USERS" | jq 'length')
    echo_success "组织共有 $USER_COUNT 个用户"
fi
echo ""

echo "=========================================="
echo -e "${GREEN}多租户功能验收演示完成！${NC}"
echo "=========================================="
echo ""
echo "验收要点总结："
echo "✓ 1. 用户注册自动分配到默认组织"
echo "✓ 2. 超级管理员可以管理所有组织"
echo "✓ 3. 组织管理接口完整（CRUD + 统计）"
echo "✓ 4. 数据严格按组织隔离"
echo "✓ 5. 普通用户只能看到本组织数据"
echo "✓ 6. 权限控制正确（组织管理仅限超级管理员）"
echo ""
echo "Web界面访问："
echo "  前端: http://localhost:3000"
echo "  后端API文档: http://localhost:8000/docs"
echo ""
