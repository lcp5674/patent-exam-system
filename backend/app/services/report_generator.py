"""审查报告生成服务"""
from __future__ import annotations
from datetime import datetime
import re


# 预定义区块配置
SECTION_DEFINITIONS = {
    "header": {
        "name": "文件头部",
        "description": "国家知识产权局标题和装饰线",
        "default_content": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n           中华人民共和国国家知识产权局\n              审查意见通知书\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    },
    "basic_info": {
        "name": "基本信息",
        "description": "申请号、发明名称、申请人",
        "variables": ["application_number", "title", "applicant"]
    },
    "issues": {
        "name": "审查意见",
        "description": "问题列表（按严重程度分组）",
        "variables": ["issues_text"]
    },
    "conclusion": {
        "name": "审查结论",
        "description": "审查结论和建议",
        "variables": ["conclusion"]
    },
    "reply_requirement": {
        "name": "答复要求",
        "description": "答复时限和方式说明",
        "default_content": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n【答复要求】\n\n请申请人在收到本通知书之日起两个月内，针对上述审查意见，\n对申请文件进行修改，或者对审查意见陈述意见。"
    },
    "footer": {
        "name": "文件尾部",
        "description": "审查员、日期、装饰线",
        "variables": ["examiner", "date"]
    }
}

GRANT_SECTION_DEFINITIONS = {
    "header": {
        "name": "文件头部",
        "description": "国家知识产权局标题",
        "default_content": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n           中华人民共和国国家知识产权局\n               授权通知书\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    },
    "basic_info": {
        "name": "基本信息",
        "description": "申请号、发明名称、申请人",
        "variables": ["application_number", "title", "applicant"]
    },
    "grant_decision": {
        "name": "授权决定",
        "description": "授权说明",
        "default_content": "【授权决定】\n\n经审查，该实用新型专利申请符合《中华人民共和国专利法》\n及《专利法实施细则》的有关规定，决定授予实用新型专利权。"
    },
    "footer": {
        "name": "文件尾部",
        "description": "审查员、日期",
        "variables": ["examiner", "date"]
    }
}

REJECTION_SECTION_DEFINITIONS = {
    "header": {
        "name": "文件头部",
        "description": "国家知识产权局标题",
        "default_content": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n           中华人民共和国国家知识产权局\n              驳回决定书\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    },
    "basic_info": {
        "name": "基本信息",
        "description": "申请号、发明名称、申请人",
        "variables": ["application_number", "title", "applicant"]
    },
    "reasons": {
        "name": "驳回理由",
        "description": "驳回原因列表",
        "variables": ["reasons"]
    },
    "review_info": {
        "name": "复审程序告知",
        "description": "复审时效和方式",
        "default_content": "【复审程序告知】\n申请人对本决定不服的，可以自收到本决定之日起三个月内，\n向国家知识产权局请求复审。"
    },
    "footer": {
        "name": "文件尾部",
        "description": "审查员、日期",
        "variables": ["examiner", "date"]
    }
}


class ReportGenerator:

    @staticmethod
    def apply_template(template_content: str, variables: dict) -> str:
        """
        应用模板变量替换
        支持的变量格式: {{variable_name}}
        """
        result = template_content
        for key, value in variables.items():
            # 替换 {{key}} 或 {{ key }} 格式的变量
            pattern = r'\{\{\s*' + re.escape(key) + r'\s*\}\}'
            result = re.sub(pattern, str(value), result)
        
        # 清理未替换的变量（可选：保留或删除）
        # result = re.sub(r'\{\{.*?\}\}', '', result)
        
        return result

    @staticmethod
    def generate_from_template(template_content: str, data: dict) -> str:
        """
        使用自定义模板生成报告
        data 应包含: application_number, title, applicant, issues, examiner, date 等
        """
        # 准备变量
        now = datetime.now().strftime("%Y年%m月%d日")
        
        # 处理问题列表
        issues = data.get("issues", [])
        
        # 按严重程度分组
        errors = [i for i in issues if i.get("severity") == "error"]
        warnings = [i for i in issues if i.get("severity") == "warning"]
        infos = [i for i in issues if i.get("severity") == "info"]
        
        # 生成问题文本
        issues_text = ""
        if issues:
            if errors:
                issues_text += "\n一、必须修改的问题\n"
                for i, issue in enumerate(errors, 1):
                    issues_text += f"\n{i}. {issue.get('rule_name', '审查项目')}\n"
                    issues_text += f"   问题描述：{issue.get('description', '')}\n"
                    if issue.get('location'):
                        issues_text += f"   位置：{issue.get('location')}\n"
                    if issue.get('legal_basis'):
                        issues_text += f"   法律依据：{issue.get('legal_basis')}\n"
                    if issue.get('suggestions'):
                        suggestions = issue.get('suggestions')
                        if isinstance(suggestions, list):
                            suggestions = '；'.join(s for s in suggestions if s)
                        issues_text += f"   修改建议：{suggestions}\n"
            
            if warnings:
                issues_text += "\n二、建议修改的问题\n"
                for i, issue in enumerate(warnings, 1):
                    issues_text += f"\n{i}. {issue.get('rule_name', '审查项目')}\n"
                    issues_text += f"   问题描述：{issue.get('description', '')}\n"
                    if issue.get('location'):
                        issues_text += f"   位置：{issue.get('location')}\n"
                    if issue.get('legal_basis'):
                        issues_text += f"   法律依据：{issue.get('legal_basis')}\n"
                    if issue.get('suggestions'):
                        suggestions = issue.get('suggestions')
                        if isinstance(suggestions, list):
                            suggestions = '；'.join(s for s in suggestions if s)
                        issues_text += f"   修改建议：{suggestions}\n"
            
            if infos:
                issues_text += "\n三、参考信息\n"
                for i, issue in enumerate(infos, 1):
                    issues_text += f"\n{i}. {issue.get('rule_name', '审查项目')}\n"
                    issues_text += f"   说明：{issue.get('description', '')}\n"
        else:
            issues_text = "经审查，未发现明显问题。请继续完善申请文件。"

        # 审查结论
        if any(i.get("severity") == "error" for i in issues):
            conclusion = "审查未通过，请根据上述意见修改申请文件"
        else:
            conclusion = "建议根据上述意见优化申请文件"

        # 构建变量字典
        variables = {
            "application_number": data.get("application_number", ""),
            "title": data.get("title", ""),
            "applicant": data.get("applicant", ""),
            "examiner": data.get("examiner", "系统审查员"),
            "date": now,
            "issues_text": issues_text,
            "conclusion": conclusion,
            "issues_count": len(issues),
            "errors_count": len(errors),
            "warnings_count": len(warnings),
            "infos_count": len(infos),
        }

        return ReportGenerator.apply_template(template_content, variables)

    @staticmethod
    def generate_from_sections(section_config: list, template_type: str, data: dict) -> str:
        """使用区块配置生成报告"""
        section_map = {
            "opinion_notice": SECTION_DEFINITIONS,
            "grant_notice": GRANT_SECTION_DEFINITIONS,
            "rejection": REJECTION_SECTION_DEFINITIONS,
        }
        definitions = section_map.get(template_type, SECTION_DEFINITIONS)
        
        now = datetime.now().strftime("%Y年%m月%d日")
        issues = data.get("issues", [])
        
        errors = [i for i in issues if i.get("severity") == "error"]
        warnings = [i for i in issues if i.get("severity") == "warning"]
        infos = [i for i in issues if i.get("severity") == "info"]
        
        issues_text = ""
        if issues:
            if errors:
                issues_text += "\n一、必须修改的问题\n"
                for i, issue in enumerate(errors, 1):
                    issues_text += f"\n{i}. {issue.get('rule_name', '审查项目')}\n"
                    issues_text += f"   问题描述：{issue.get('description', '')}\n"
                    if issue.get('location'):
                        issues_text += f"   位置：{issue.get('location')}\n"
                    if issue.get('suggestions'):
                        suggestions = issue.get('suggestions')
                        if isinstance(suggestions, list):
                            suggestions = '；'.join(s for s in suggestions if s)
                        issues_text += f"   修改建议：{suggestions}\n"
            
            if warnings:
                issues_text += "\n二、建议修改的问题\n"
                for i, issue in enumerate(warnings, 1):
                    issues_text += f"\n{i}. {issue.get('rule_name', '审查项目')}\n"
                    issues_text += f"   问题描述：{issue.get('description', '')}\n"
                    if issue.get('location'):
                        issues_text += f"   位置：{issue.get('location')}\n"
                    if issue.get('suggestions'):
                        suggestions = issue.get('suggestions')
                        if isinstance(suggestions, list):
                            suggestions = '；'.join(s for s in suggestions if s)
                        issues_text += f"   修改建议：{suggestions}\n"
            
            if infos:
                issues_text += "\n三、参考信息\n"
                for i, issue in enumerate(infos, 1):
                    issues_text += f"\n{i}. {issue.get('rule_name', '审查项目')}\n"
                    issues_text += f"   说明：{issue.get('description', '')}\n"
        else:
            issues_text = "经审查，未发现明显问题。请继续完善申请文件。"

        conclusion = "审查未通过，请根据上述意见修改申请文件" if any(i.get("severity") == "error" for i in issues) else "建议根据上述意见优化申请文件"

        variables = {
            "application_number": data.get("application_number", ""),
            "title": data.get("title", ""),
            "applicant": data.get("applicant", ""),
            "examiner": data.get("examiner", "系统审查员"),
            "date": now,
            "issues_text": issues_text,
            "conclusion": conclusion,
            "issues_count": len(issues),
            "errors_count": len(errors),
            "warnings_count": len(warnings),
            "infos_count": len(infos),
            "reasons": data.get("reasons", ""),
        }

        sorted_sections = sorted(section_config, key=lambda x: x.get("order", 0))
        report_parts = []
        
        for section in sorted_sections:
            if not section.get("enabled", True):
                continue
            
            section_id = section.get("id")
            section_def = definitions.get(section_id, {})
            content = section.get("custom_content") or section_def.get("default_content", "")
            
            if content:
                content = ReportGenerator.apply_template(content, variables)
                report_parts.append(content)
        
        return "\n\n".join(report_parts)

    @staticmethod
    def generate_opinion_notice(application_number: str, title: str, applicant: str,
                                issues: list[dict], examiner: str = "系统审查员") -> str:
        now = datetime.now().strftime("%Y年%m月%d日")
        
        # 清理标题中的文件扩展名
        if title and title.endswith('.doc'):
            title = title[:-4]
        elif title and title.endswith('.pdf'):
            title = title[:-4]
        elif title and title.endswith('.txt'):
            title = title[:-4]
        
        if not issues:
            issues_text = "经审查，未发现明显问题。请继续完善申请文件。"
        else:
            issues_text = ""
            # 按严重程度分组
            errors = [i for i in issues if i.get("severity") == "error"]
            warnings = [i for i in issues if i.get("severity") == "warning"]
            infos = [i for i in issues if i.get("severity") == "info"]
            
            # 错误级别问题
            if errors:
                issues_text += "\n一、必须修改的问题\n"
                for i, issue in enumerate(errors, 1):
                    issues_text += f"\n{i}. {issue.get('rule_name', '审查项目')}\n"
                    issues_text += f"   问题描述：{issue.get('description', '')}\n"
                    if issue.get('location'):
                        issues_text += f"   位置：{issue.get('location')}\n"
                    if issue.get('legal_basis'):
                        issues_text += f"   法律依据：{issue.get('legal_basis')}\n"
                    if issue.get('suggestions'):
                        suggestions = issue.get('suggestions')
                        if isinstance(suggestions, list):
                            suggestions = '；'.join(s for s in suggestions if s)
                        issues_text += f"   修改建议：{suggestions}\n"
            
            # 警告级别问题
            if warnings:
                issues_text += "\n二、建议修改的问题\n"
                for i, issue in enumerate(warnings, 1):
                    issues_text += f"\n{i}. {issue.get('rule_name', '审查项目')}\n"
                    issues_text += f"   问题描述：{issue.get('description', '')}\n"
                    if issue.get('location'):
                        issues_text += f"   位置：{issue.get('location')}\n"
                    if issue.get('legal_basis'):
                        issues_text += f"   法律依据：{issue.get('legal_basis')}\n"
                    if issue.get('suggestions'):
                        suggestions = issue.get('suggestions')
                        if isinstance(suggestions, list):
                            suggestions = '；'.join(s for s in suggestions if s)
                        issues_text += f"   修改建议：{suggestions}\n"
            
            # 信息级别问题
            if infos:
                issues_text += "\n三、参考信息\n"
                for i, issue in enumerate(infos, 1):
                    issues_text += f"\n{i}. {issue.get('rule_name', '审查项目')}\n"
                    issues_text += f"   说明：{issue.get('description', '')}\n"

        # 使用字符串拼接避免f-string的换行符问题
        report = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += "           中华人民共和国国家知识产权局\n"
        report += "              审查意见通知书\n"
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        report += f"申请号：{application_number}\n"
        report += f"发明名称：{title}\n"
        report += f"申请人：{applicant}\n\n"
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        report += "【审查意见】\n\n"
        report += "经审查，该实用新型专利申请存在以下问题：\n"
        report += issues_text + "\n\n"
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        report += "【审查结论】\n\n"
        
        if any(i.get("severity") == "error" for i in issues):
            report += "审查未通过，请根据上述意见修改申请文件\n\n"
        else:
            report += "建议根据上述意见优化申请文件\n\n"
        
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        report += "【答复要求】\n\n"
        report += "请申请人在收到本通知书之日起两个月内，针对上述审查意见，\n"
        report += "对申请文件进行修改，或者对审查意见陈述意见。\n\n"
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += f"审查员：{examiner}\n"
        report += f"日期：{now}\n"
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        return report

    @staticmethod
    def generate_grant_notice(application_number: str, title: str, applicant: str, examiner: str = "系统审查员") -> str:
        now = datetime.now().strftime("%Y年%m月%d日")
        
        # 清理标题中的文件扩展名
        if title and title.endswith('.doc'):
            title = title[:-4]
        elif title and title.endswith('.pdf'):
            title = title[:-4]
        elif title and title.endswith('.txt'):
            title = title[:-4]
        
        return f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
           中华人民共和国国家知识产权局
               授权通知书
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

申请号：{application_number}
发明名称：{title}
申请人：{applicant}

【授权决定】

经审查，该实用新型专利申请符合《中华人民共和国专利法》
及《专利法实施细则》的有关规定，决定授予实用新型专利权。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
审查员：{examiner}
日期：{now}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    @staticmethod
    def generate_rejection_decision(application_number: str, title: str, applicant: str,
                                    reasons: list[str], examiner: str = "系统审查员") -> str:
        now = datetime.now().strftime("%Y年%m月%d日")
        
        # 清理标题中的文件扩展名
        if title and title.endswith('.doc'):
            title = title[:-4]
        elif title and title.endswith('.pdf'):
            title = title[:-4]
        elif title and title.endswith('.txt'):
            title = title[:-4]
        
        reasons_text = "\n".join(f"{i+1}. {r}" for i, r in enumerate(reasons))
        return f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
           中华人民共和国国家知识产权局
              驳回决定书
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

申请号：{application_number}
发明名称：{title}
申请人：{applicant}

【驳回理由】
{reasons_text}

【复审程序告知】
申请人对本决定不服的，可以自收到本决定之日起三个月内，
向国家知识产权局请求复审。

审查员：{examiner}
日期：{now}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
