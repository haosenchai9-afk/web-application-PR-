#!/usr/bin/env python3
# =============================================================================
# GitHub PR Automation Workflow Verification Script（样例：web-application仓库）
# =============================================================================
# 验证目标：web-application仓库的PR自动化工作流（pr-automation.yml）
# 依赖：requests, python-dotenv, base64，需提前配置 .github_env 环境变量
# =============================================================================

import sys
import os
import requests
import time
import datetime
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
import base64


# -----------------------------
# 1) 配置参数（已替换为web-application仓库实际值）
# -----------------------------
CONFIG = {
    # 代码平台基础配置（GitHub固定）
    "CODE_PLATFORM": {
        "name": "GitHub",
        "api_domain": "github.com",
        "auth_scheme": "token",
        "default_repo": "web-template-repo",  # 团队默认测试仓库
        "target_repo": "web-application",     # 目标验证仓库
        "api_per_page": 100,                  # 单次API最大返回100条数据
        "max_workflow_wait": 600              # 主PR工作流最大等待10分钟（600秒）
    },

    # 环境与认证配置（.github_env存储敏感信息）
    "ENVIRONMENT": {
        "env_file": ".github_env",            # 环境变量文件
        "token_var": "GITHUB_TOKEN",          # Token变量名
        "org_var": "GITHUB_ORG"               # 组织变量名（值为"web-dev-team"）
    },

    # 工作流配置（PR自动化工作流具体信息）
    "WORKFLOW": {
        "file_path": ".github/workflows/pr-automation.yml",  # 工作流文件路径
        "workflow_filename": "pr-automation.yml",            # 工作流文件名
        "required_triggers": ["opened", "synchronize", "reopened"],  # 必需触发事件
        "required_jobs": [                              # 必需作业（4类核心校验）
            "code-quality", "testing-suite", 
            "security-scan", "build-validation"
        ],
        "parallel_check_threshold": 120                 # 作业并行判定阈值：120秒
    },

    # 主PR配置（实现PR自动化的核心PR）
    "MAIN_PR": {
        "title": "feat: add PR automation workflow (code-quality/test/security/build)",  # PR标题
        "source_branch": "feat/pr-automation",          # 源分支（开发分支）
        "target_branch": "main"                         # 目标分支（主分支）
    },

    # 单元测试配置（4类失败场景测试用例）
    "UNIT_TEST": {
        "test_cases": [
            # 用例1：代码质量失败（ESLint违规：未声明变量直接使用）
            {
                "title": "Test: Code Quality Failure (ESLint Error)",
                "branch": "test-code-quality-fail",
                "file_path": "src/utils/test-lint-fail.js",
                "content": "// 故意触发ESLint no-undef规则（未声明变量）\nconsole.log(undefinedVar);",
                "expected_failure": "code-quality"  # 预期失败作业
            },
            # 用例2：测试执行失败（Jest断言错误：1≠2）
            {
                "title": "Test: Testing Suite Failure (Jest Assert Error)",
                "branch": "test-testing-fail",
                "file_path": "tests/utils/test-fail.test.js",
                "content": "// 故意触发Jest断言失败\nconst sum = (a,b) => a+b;\ntest('sum 1+1 should be 2', () => {\nexpect(sum(1,1)).toBe(3); // 错误：预期2实际3\n});",
                "expected_failure": "testing-suite"  # 预期失败作业
            },
            # 用例3：安全扫描失败（硬编码API密钥）
            {
                "title": "Test: Security Scan Failure (Hardcoded Secret)",
                "branch": "test-security-fail",
                "file_path": "src/api/security-test.js",
                "content": "// 故意触发安全扫描：硬编码API密钥\nconst apiKey = 'sk_test_1234567890abcdef'; // 敏感信息硬编码",
                "expected_failure": "security-scan"  # 预期失败作业
            },
            # 用例4：构建验证失败（引用不存在的依赖包）
            {
                "title": "Test: Build Validation Failure (Missing Dependency)",
                "branch": "test-build-fail",
                "file_path": "src/components/test-build-fail.js",
                "content": "// 故意触发构建失败：引用不存在的依赖\nimport nonExistentLib from 'non-existent-lib';\nconst TestComponent = () => <div>{nonExistentLib.render()}</div>;\nexport default TestComponent;",
                "expected_failure": "build-validation"  # 预期失败作业
            }
        ],
        "max_test_wait": 300,  # 测试PR工作流最大等待5分钟（300秒）
        "cleanup_enabled": True  # 测试后自动清理PR和分支
    },

    # PR评论自动化配置（机器人及必需报告）
    "PR_COMMENT": {
        "bot_login": "github-actions[bot]",  # GitHub Actions默认机器人账号
        "required_reports": [                # 必需的4类自动化报告
            {
                "name": "Code Quality Report",  # 代码质量报告
                "main_keywords": ["Code Quality Check Results", "ESLint"],  # 主关键词
                "sub_keywords": ["Pass Rate: 100%", "Total Issues: 0"]       # 子关键词（无错误）
            },
            {
                "name": "Test Coverage Report",  # 测试覆盖率报告
                "main_keywords": ["Test Coverage Results", "Jest"],
                "sub_keywords": ["Coverage: 85%+"]
            },
            {
                "name": "Security Scan Report",  # 安全扫描报告
                "main_keywords": ["Security Scan Results", "Secret Detection"],
                "sub_keywords": ["No Secrets Found"]
            },
            {
                "name": "Build Validation Report",  # 构建验证报告
                "main_keywords": ["Build Check Results", "Webpack"],
                "sub_keywords": ["Build Successful"]
            }
        ]
    }
}


# -----------------------------
# 2) 工具函数（GitHub API交互与基础操作，通用无需修改）
# -----------------------------
def _get_github_api(
    endpoint: str, headers: Dict[str, str], owner: str, repo: str
) -> Tuple[bool, Optional[Dict]]:
    """调用GitHub API（GET），返回（成功状态，响应数据）"""
    url = f"https://api.{CONFIG['CODE_PLATFORM']['api_domain']}/repos/{owner}/{repo}/{endpoint}"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return True, response.json()
        elif response.status_code == 404:
            print(f"API信息: {endpoint} 未找到 (404)", file=sys.stderr)
            return False, None
        else:
            print(f"API错误 ({endpoint}): 状态码 {response.status_code} - {response.text[:100]}", file=sys.stderr)
            return False, None
    except Exception as e:
        print(f"API调用异常 ({endpoint}): {str(e)}", file=sys.stderr)
        return False, None


def _post_github_api(
    endpoint: str, headers: Dict[str, str], owner: str, repo: str, data: Dict
) -> Tuple[bool, Optional[Dict]]:
    """调用GitHub API（POST），返回（成功状态，响应数据）"""
    url = f"https://api.{CONFIG['CODE_PLATFORM']['api_domain']}/repos/{owner}/{repo}/{endpoint}"
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code in [200, 201]:
            return True, response.json()
        else:
            print(f"API错误 ({endpoint}): 状态码 {response.status_code} - {response.text[:100]}", file=sys.stderr)
            return False, None
    except Exception as e:
        print(f"API调用异常 ({endpoint}): {str(e)}", file=sys.stderr)
        return False, None


def _patch_github_api(
    endpoint: str, headers: Dict[str, str], owner: str, repo: str, data: Dict
) -> Tuple[bool, Optional[Dict]]:
    """调用GitHub API（PATCH），返回（成功状态，响应数据）"""
    url = f"https://api.{CONFIG['CODE_PLATFORM']['api_domain']}/repos/{owner}/{repo}/{endpoint}"
    try:
        response = requests.patch(url, headers=headers, json=data)
        if response.status_code == 200:
            return True, response.json()
        else:
            print(f"API错误 ({endpoint}): 状态码 {response.status_code} - {response.text[:100]}", file=sys.stderr)
            return False, None
    except Exception as e:
        print(f"API调用异常 ({endpoint}): {str(e)}", file=sys.stderr)
        return False, None


def _get_file_content(
    file_path: str,
    headers: Dict[str, str],
    owner: str,
    repo: str,
    ref: str = "main",  # 默认从main分支获取
) -> Optional[str]:
    """从指定分支获取文件内容（Base64解码）"""
    success, result = _get_github_api(
        f"contents/{file_path}?ref={ref}", headers, owner, repo
    )
    if not success or not result:
        return None

    try:
        content = base64.b64decode(result.get("content", "")).decode("utf-8")
        return content
    except Exception as e:
        print(f"文件解码错误 ({file_path}): {e}", file=sys.stderr)
        return None


def _find_pr_by_title(
    title: str, headers: Dict[str, str], owner: str, repo: str
) -> Optional[Dict]:
    """通过精确标题匹配查找PR（支持已关闭/打开状态）"""
    for state in ["closed", "open"]:
        success, prs = _get_github_api(
            f"pulls?state={state}&per_page={CONFIG['CODE_PLATFORM']['api_per_page']}", headers, owner, repo
        )
        if success and prs:
            for pr in prs:
                if pr.get("title") == title:
                    return pr
    return None


def _wait_for_workflow_completion(
    headers: Dict[str, str],
    owner: str,
    repo: str,
    max_wait: int = None
) -> bool:
    """等待指定工作流完成（默认使用CONFIG中的max_workflow_wait）"""
    workflow_file = CONFIG["WORKFLOW"]["workflow_filename"]
    max_wait = max_wait or CONFIG["CODE_PLATFORM"]["max_workflow_wait"]
    print(f"⏳ 等待 {workflow_file} 工作流完成...")

    start_time = time.time()
    no_workflow_check_count = 0

    while time.time() - start_time < max_wait:
        try:
            success, response = _get_github_api(
                f"actions/workflows/{workflow_file}/runs?per_page=10",
                headers,
                owner,
                repo,
            )

            if success and response:
                runs = response.get("workflow_runs", [])
                if len(runs) > 0:
                    running_count = 0
                    completed_count = 0

                    # 检查最近5次运行（避免历史运行干扰）
                    for run in runs[:5]:
                        status = run["status"]
                        if status == "completed":
                            completed_count += 1
                        elif status in ["in_progress", "queued"]:
                            running_count += 1

                    print(f"   状态: {completed_count} 已完成, {running_count} 运行中/排队中")

                    if running_count == 0:
                        print(f"✅ 所有 {workflow_file} 工作流已完成")
                        return True
                else:
                    # 未找到工作流运行记录
                    no_workflow_check_count += 1
                    if no_workflow_check_count == 1:
                        print("   暂未找到工作流运行记录，等待5秒后重试...")
                        time.sleep(5)
                        continue
                    elif no_workflow_check_count >= 2:
                        print(f"⚠️ 两次检查均未找到 {workflow_file} 运行记录，可能未触发工作流")
                        print("   继续执行后续验证...")
                        return False

            print(f"⏳ 仍在等待... ({int(time.time() - start_time)}秒已过去)")
            time.sleep(10)

        except Exception as e:
            print(f"⚠️ 检查工作流状态出错: {e}")
            time.sleep(10)

    print(f"⚠️ 工作流等待超时（超过 {max_wait} 秒）")
    return False


# -----------------------------
# 3) 核心校验函数（按校验维度拆分，通用无需修改）
# -----------------------------
def _validate_environment() -> Dict[str, str]:
    """加载并验证环境变量（Token、组织名）"""
    env_config = CONFIG["ENVIRONMENT"]
    load_dotenv(env_config["env_file"])
    
    token = os.environ.get(env_config["token_var"])
    org = os.environ.get(env_config["org_var"])
    
    if not token:
        print(f"错误: 环境变量 {env_config['token_var']} 未在 {env_config['env_file']} 中设置", file=sys.stderr)
        sys.exit(1)
    if not org:
        print(f"错误: 环境变量 {env_config['org_var']} 未在 {env_config['env_file']} 中设置", file=sys.stderr)
        sys.exit(1)
        
    return {"token": token, "org": org}


def _verify_workflow_file(
    headers: Dict[str, str], owner: str, repo: str
) -> Tuple[bool, List[str]]:
    """校验工作流文件是否存在及内容合规（触发事件、必需作业）"""
    print("\n📄 校验工作流文件...")
    errors = []
    workflow_config = CONFIG["WORKFLOW"]
    workflow_path = workflow_config["file_path"]

    # 1. 检查工作流文件是否存在（从主PR目标分支获取）
    workflow_content = _get_file_content(
        workflow_path, headers, owner, repo, ref=CONFIG["MAIN_PR"]["target_branch"]
    )
    if not workflow_content:
        return False, [f"工作流文件 {workflow_path} 在 {CONFIG['MAIN_PR']['target_branch']} 分支中未找到"]
    print(f"   ✅ 工作流文件 {workflow_path} 存在")

    # 2. 校验PR触发事件配置
    if f"pull_request:" not in workflow_content:
        errors.append("工作流缺少 pull_request 触发配置")
    else:
        print("   ✅ 找到 pull_request 触发配置")

    # 校验必需触发事件
    missing_triggers = [t for t in workflow_config["required_triggers"] if t not in workflow_content]
    if missing_triggers:
        errors.append(f"缺少必需触发事件: {missing_triggers}")
    else:
        print(f"   ✅ 找到所有必需触发事件: {workflow_config['required_triggers']}")

    # 3. 校验必需作业
    missing_jobs = [j for j in workflow_config["required_jobs"] if f"{j}:" not in workflow_content]
    if missing_jobs:
        errors.append(f"缺少必需作业: {missing_jobs}")
    else:
        print(f"   ✅ 找到所有必需作业: {workflow_config['required_jobs']}")

    return len(errors) == 0, errors


def _verify_main_pr_merged(
    headers: Dict[str, str], owner: str, repo: str
) -> Tuple[bool, List[str], Optional[Dict]]:
    """校验实现PR自动化的主PR是否已合并（源分支、目标分支合规）"""
    print("\n🔍 校验主PR合并状态...")
    errors = []
    pr_config = CONFIG["MAIN_PR"]

    # 1. 查找主PR
    pr = _find_pr_by_title(pr_config["title"], headers, owner, repo)
    if not pr:
        return False, [f"主PR '{pr_config['title']}' 未找到"], None
    pr_number = pr["number"]
    print(f"   找到主PR #{pr_number}")

    # 2. 校验PR是否已合并
    if not pr.get("merged_at", False):
        errors.append(f"PR #{pr_number} 未合并")
    else:
        print(f"   ✅ PR #{pr_number} 已合并")

    # 3. 校验源分支
    if pr.get("head", {}).get("ref") != pr_config["source_branch"]:
        errors.append(f"PR #{pr_number} 源分支应为 {pr_config['source_branch']}，实际为 {pr.get('head', {}).get('ref')}")
    else:
        print(f"   ✅ PR 源分支正确: {pr_config['source_branch']}")

    # 4. 校验目标分支
    if pr.get("base", {}).get("ref") != pr_config["target_branch"]:
        errors.append(f"PR #{pr_number} 目标分支应为 {pr_config['target_branch']}，实际为 {pr.get('base', {}).get('ref')}")
    else:
        print(f"   ✅ PR 目标分支正确: {pr_config['target_branch']}")

    return len(errors) == 0, errors, pr


def _verify_workflow_runs(
    pr_data: Dict, headers: Dict[str, str], owner: str, repo: str
) -> Tuple[bool, List[str]]:
    """校验主PR的工作流运行状态（作业存在、成功、并行执行）"""
    print("\n⚙️ 校验工作流运行状态...")
    errors = []
    workflow_config = CONFIG["WORKFLOW"]
    pr_number = pr_data["number"]
    pr_head_sha = pr_data.get("head", {}).get("sha")
    pr_head_ref = pr_data.get("head", {}).get("ref")

    # 1. 获取主PR关联的工作流运行记录
    success, runs_response = _get_github_api(
        f"actions/runs?event=pull_request&per_page={CONFIG['CODE_PLATFORM']['api_per_page']}", headers, owner, repo
    )
    if not success:
        return False, ["获取工作流运行记录失败"]

    # 筛选主PR的运行记录（通过SHA或分支匹配）
    pr_runs = []
    for run in runs_response.get("workflow_runs", []):
        if pr_head_sha and run.get("head_sha") == pr_head_sha:
            pr_runs.append(run)
            continue
        if pr_head_ref and run.get("head_branch") == pr_head_ref:
            pr_runs.append(run)
            continue

    if not pr_runs:
        return False, [f"未找到PR #{pr_number} 的工作流运行记录（SHA: {pr_head_sha}，分支: {pr_head_ref}）"]
    print(f"   找到 PR #{pr_number} 的 {len(pr_runs)} 条工作流运行记录")

    # 2. 校验最新运行是否成功
    latest_run = pr_runs[0]  # GitHub按创建时间降序返回，取第一条为最新
    run_id = latest_run["id"]
    if latest_run["conclusion"] != "success":
        errors.append(f"最新工作流运行（ID: {run_id}）未成功，结论: {latest_run['conclusion']}")
    else:
        print(f"   ✅ 最新工作流运行（ID: {run_id}）成功")

    # 3. 校验必需作业是否存在且成功
    success, jobs_response = _get_github_api(f"actions/runs/{run_id}/jobs", headers, owner, repo)
    if not success:
        return False, [f"获取工作流运行（ID: {run_id}）的作业记录失败"]

    jobs = jobs_response.get("jobs", [])
    found_jobs = [job["name"] for job in jobs]
    missing_jobs = [j for j in workflow_config["required_jobs"] if j not in found_jobs]
    if missing_jobs:
        errors.append(f"缺少必需作业: {missing_jobs}，已找到: {found_jobs}")
    else:
        print(f"   ✅ 找到所有必需作业: {found_jobs}")

    # 校验所有作业是否成功
    failed_jobs = [job["name"] for job in jobs if job["conclusion"] != "success"]
    if failed_jobs:
        errors.append(f"以下作业执行失败: {failed_jobs}")
    else:
        print("   ✅ 所有作业执行成功")

    # 4. 校验作业是否并行执行（启动时间差≤阈值）
    if len(jobs) >= len(workflow_config["required_jobs"]):
        start_times = [job["started_at"] for job in jobs if job["started_at"]]
        if len(start_times) >= len(workflow_config["required_jobs"]):
            start_dt = [datetime.datetime.fromisoformat(t.replace("Z", "+00:00")) for t in start_times]
            time_diff = (max(start_dt) - min(start_dt)).total_seconds()
            if time_diff > workflow_config["parallel_check_threshold"]:
                errors.append(f"作业未并行执行（时间差: {time_diff:.0f}秒，阈值: {workflow_config['parallel_check_threshold']}秒）")
            else:
                print(f"   ✅ 作业并行执行（时间差: {time_diff:.0f}秒）")
        else:
            errors.append("作业启动时间不足，无法验证并行执行")

    return len(errors) == 0, errors


def _verify_pr_comments(
    pr_data: Dict, headers: Dict[str, str], owner: str, repo: str
) -> Tuple[bool, List[str]]:
    """校验PR是否包含自动化机器人的必需报告评论"""
    print("\n💬 校验PR自动化评论...")
    errors = []
    comment_config = CONFIG["PR_COMMENT"]
    pr_number = pr_data["number"]

    # 1. 获取PR评论
    success, comments = _get_github_api(f"issues/{pr_number}/comments", headers, owner, repo)
    if not success:
        return False, ["获取PR评论失败"]

    # 筛选自动化机器人的评论
    bot_comments = [c for c in comments if c.get("user", {}).get("login") == comment_config["bot_login"]]
    if not bot_comments:
        return False, [f"未找到 {comment_config['bot_login']} 的评论"]
    print(f"   找到 {comment_config['bot_login']} 的 {len(bot_comments)} 条评论")

    # 2. 校验必需报告是否齐全
    bot_comment_bodies = [c.get("body", "") for c in bot_comments]
    required_reports = comment_config["required_reports"]
    found_reports = []

    for report in required_reports:
        report_found = False
        for body in bot_comment_bodies:
            if any(keyword in body for keyword in report["main_keywords"]):
                report_found = True
                # 校验子关键词（可选）
                missing_sub = [k for k in report["sub_keywords"] if k not in body]
                if missing_sub:
                    errors.append(f"{report['name']} 缺少子关键词: {missing_sub}")
                else:
                    print(f"   ✅ 找到 {report['name']}")
                break
        if not report_found:
            errors.append(f"缺少 {report['name']}（主关键词: {report['main_keywords']}）")
        else:
            found_reports.append(report["name"])

    # 校验报告数量是否符合预期
    if len(found_reports) != len(required_reports):
        errors.append(f"预期 {len(required_reports)} 份报告，实际找到 {len(found_reports)} 份")
    else:
        print(f"   ✅ 所有 {len(required_reports)} 份必需报告齐全")

    return len(errors) == 0, errors


def _run_unit_tests(
    headers: Dict[str, str], owner: str, repo: str
) -> Tuple[bool, List[str]]:
    """创建含故意错误的测试PR，校验工作流是否正确识别失败场景"""
    print("\n🧪 执行失败场景单元测试...")
    errors = []
    test_config = CONFIG["UNIT_TEST"]
    created_prs = []

    # 遍历所有测试用例
    for idx, test_case in enumerate(test_config["test_cases"]):
        print(f"\n   处理测试用例 {idx+1}: {test_case['title']}")

        # 1. 创建测试分支（若已存在则删除重建）
        branch = test_case["branch"]
        # 获取目标分支的SHA（用于创建新分支）
        success, target_ref = _get_github_api(
            f"git/ref/heads/{CONFIG['MAIN_PR']['target_branch']}", headers, owner, repo
        )
        if not success:
            errors.append(f"测试用例 {idx+1} 失败: 无法获取 {CONFIG['MAIN_PR']['target_branch']} 分支的引用")
            continue

        target_sha = target_ref["object"]["sha"]
        branch_data = {"ref": f"refs/heads/{branch}", "sha": target_sha}

        # 尝试创建分支，若已存在则删除后重试
        success, _ = _post_github_api("git/refs", headers, owner, repo, branch_data)
        if not success:
            print(f"   分支 {branch} 已存在，尝试删除后重建...")
            # 删除已存在的分支
            delete_url = f"https://api.{CONFIG['CODE_PLATFORM']['api_domain']}/repos/{owner}/{repo}/git/refs/heads/{branch}"
            delete_response = requests.delete(delete_url, headers=headers)
            if delete_response.status_code != 204:
                errors.append(f"测试用例 {idx+1} 失败: 无法删除已存在的分支 {branch}")
                continue
            time.sleep(2)  # 等待2秒确保删除生效
            # 重新创建分支
            success, _ = _post_github_api("git/refs", headers, owner, repo, branch_data)
            if not success:
                errors.append(f"测试用例 {idx+1} 失败: 重建分支 {branch} 失败")
                continue
        print(f"   ✅ 成功创建测试分支 {branch}")

        # 2. 创建/更新测试文件（含故意错误）
        file_path = test_case["file_path"]
        file_content = base64.b64encode(test_case["content"].encode()).decode()
        file_data = {
            "message": f"测试提交: {test_case['title']}",
            "content": file_content,
            "branch": branch
        }

        # 检查文件是否已存在（存在则需传入SHA更新）
        success, file_info = _get_github_api(f"contents/{file_path}?ref={CONFIG['MAIN_PR']['target_branch']}", headers, owner, repo)
        if success and file_info:
            file_data["sha"] = file_info["sha"]

        # 上传文件（PUT方法支持创建/更新）
        file_url = f"https://api.{CONFIG['CODE_PLATFORM']['api_domain']}/repos/{owner}/{repo}/contents/{file_path}"
        try:
            response = requests.put(file_url, headers=headers, json=file_data)
            if response.status_code not in [200, 201]:
                errors.append(f"测试用例 {idx+1} 失败: 上传文件 {file_path} 失败（状态码: {response.status_code}）")
                continue
        except Exception as e:
            errors.append(f"测试用例 {idx+1} 失败: 上传文件 {file_path} 异常: {str(e)}")
            continue
        print(f"   ✅ 成功上传测试文件 {file_path}")

        # 3. 创建测试PR
        pr_data = {
            "title": test_case["title"],
            "head": branch,
            "base": CONFIG["MAIN_PR"]["target_branch"],
            "body": f"测试PR: 验证工作流是否正确识别 {test_case['expected_failure']} 失败场景"
        }
        success, pr_response = _post_github_api("pulls", headers, owner, repo, pr_data)
        if not success:
            errors.append(f"测试用例 {idx+1} 失败: 创建测试PR失败")
            continue
        pr_number = pr_response["number"]
        created_prs.append({"number": pr_number, "branch": branch})
        print(f"   ✅ 成功创建测试PR #{pr_number}")

    # 4. 等待测试PR的工作流完成并校验结果
    if created_prs:
        print(f"\n   等待 {len(created_prs)} 个测试PR的工作流完成（最大等待 {test_config['max_test_wait']} 秒）...")
        time.sleep(5)  # 等待工作流触发
        _wait_for_workflow_completion(headers, owner, repo, max_wait=test_config["max_test_wait"])

        # 校验每个测试PR的工作流是否正确失败
        for idx, pr_info in enumerate(created_prs):
            pr_number = pr_info["number"]
            test_case = test_config["test_cases"][idx]
            # 获取PR的工作流运行记录
            success, runs_response = _get_github_api(
                f"actions/runs?event=pull_request&per_page=5", headers, owner, repo
            )
            if not success:
                errors.append(f"测试PR #{pr_number} 校验失败: 无法获取工作流记录")
                continue

            # 筛选该PR的运行记录
            pr_runs = []
            for run in runs_response.get("workflow_runs", []):
                for pr in run.get("pull_requests", []):
                    if pr.get("number") == pr_number:
                        pr_runs.append(run)
                        break

            if not pr_runs:
                errors.append(f"测试PR #{pr_number} 校验失败: 未找到工作流记录")
                continue

            # 校验最新运行是否失败
            latest_run = pr_runs[0]
            if latest_run["conclusion"] != "failure":
                errors.append(f"测试PR #{pr_number} 校验失败: 预期 {test_case['expected_failure']} 失败，实际结论: {latest_run['conclusion']}")
            else:
                print(f"   ✅ 测试PR #{pr_number} 正确识别 {test_case['expected_failure']} 失败场景")

    # 5. 清理测试PR和分支（若启用清理）
    if test_config["cleanup_enabled"] and created_prs:
        print("\n   清理测试PR和分支...")
        for pr_info in created_prs:
            pr_number = pr_info["number"]
            branch = pr_info["branch"]
            # 关闭PR
            success, _ = _patch_github_api(f"pulls/{pr_number}", headers, owner, repo, {"state": "closed"})
            if success:
                print(f"   ✅ 关闭测试PR #{pr_number}")
            else:
                errors.append(f"清理失败: 无法关闭测试PR #{pr_number}")
            # 删除分支
            delete_url = f"https://api.{CONFIG['CODE_PLATFORM']['api_domain']}/repos/{owner}/{repo}/git/refs/heads/{branch}"
            delete_response = requests.delete(delete_url, headers=headers)
            if delete_response.status_code == 204:
                print(f"   ✅ 删除测试分支 {branch}")
            else:
                errors.append(f"清理失败: 无法删除测试分支 {branch}")

    return len(errors) == 0, errors


# -----------------------------
# 4) 主校验流程（通用无需修改）
# -----------------------------
def verify_pr_automation_workflow() -> bool:
    """执行PR自动化工作流的完整校验"""
    # 1. 加载环境配置
    print("🔍 启动PR自动化工作流验证（样例：web-application仓库）")
    print("=" * 60)
    print("1. 加载环境配置...")
    env_data = _validate_environment()
    github_token = env_data["token"]
    github_org = env_data["org"]
    repo = CONFIG["CODE_PLATFORM"]["target_repo"]

    # 构建API请求头
    headers = {
        "Authorization": f"{CONFIG['CODE_PLATFORM']['auth_scheme']} {github_token}",
        "Accept": f"application/vnd.{CONFIG['CODE_PLATFORM']['api_domain'].split('.')[0]}.v3+json"
    }
    print("✓ 环境配置加载成功")

    # 2. 执行各维度校验
    all_passed = True
    pr_data = None

    # 2.1 校验工作流文件
    workflow_ok, workflow_errors = _verify_workflow_file(headers, github_org, repo)
    if not workflow_ok:
        all_passed = False
        print("❌ 工作流文件校验失败:")
        for err in workflow_errors:
            print(f"   - {err}")
    else:
        print("✅ 工作流文件校验通过")

    # 2.2 校验主PR合并状态
    pr_ok, pr_errors, pr_data = _verify_main_pr_merged(headers, github_org, repo)
    if not pr_ok:
        all_passed = False
        print("❌ 主PR校验失败:")
        for err in pr_errors:
            print(f"   - {err}")
    else:
        print("✅ 主PR校验通过")

    # 2.3 校验工作流运行状态（仅主PR校验通过时执行）
    if pr_ok and pr_data:
        runs_ok, runs_errors = _verify_workflow_runs(pr_data, headers, github_org, repo)
        if not runs_ok:
            all_passed = False
            print("❌ 工作流运行校验失败:")
            for err in runs_errors:
                print(f"   - {err}")
        else:
            print("✅ 工作流运行校验通过")

        # 2.4 校验PR自动化评论（仅主PR校验通过时执行）
        comments_ok, comments_errors = _verify_pr_comments(pr_data, headers, github_org, repo)
        if not comments_ok:
            all_passed = False
            print("❌ PR评论校验失败:")
            for err in comments_errors:
                print(f"   - {err}")
        else:
            print("✅ PR评论校验通过")

    # 2.5 执行失败场景单元测试
    tests_ok, tests_errors = _run_unit_tests(headers, github_org, repo)
    if not tests_ok:
        all_passed = False
        print("❌ 单元测试失败:")
        for err in tests_errors:
            print(f"   - {err}")
    else:
        print("✅ 单元测试通过")

    # 3. 输出最终结果
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有PR自动化工作流校验通过!（样例：web-application仓库）")
        print("\n📋 校验总结:")
        print(f"   ✅ 工作流文件 {CONFIG['WORKFLOW']['file_path']} 合规（含触发事件+4类作业）")
        print(f"   ✅ 主PR #{pr_data['number']} 从 {CONFIG['MAIN_PR']['source_branch']} 合并到 {CONFIG['MAIN_PR']['target_branch']}")
        print(f"   ✅ 工作流运行成功，4类作业并行执行（时间差≤{CONFIG['WORKFLOW']['parallel_check_threshold']}秒）")
        print(f"   ✅ PR含 {len(CONFIG['PR_COMMENT']['required_reports'])} 类自动化报告（{CONFIG['PR_COMMENT']['bot_login']} 机器人）")
        print(f"   ✅ 4类失败场景测试通过（工作流正确拦截错误PR）")
        print(f"\n🤖 web-application仓库PR自动化工作流运行正常!")
    else:
        print("❌ PR自动化工作流校验失败!（样例：web-application仓库）")
        print("   部分校验项未满足预期要求，请根据错误信息修正。")

    return all_passed


# -----------------------------
# 5) 脚本入口
# -----------------------------
if __name__ == "__main__":
    success = verify_pr_automation_workflow()
    sys.exit(0 if success else 1)
