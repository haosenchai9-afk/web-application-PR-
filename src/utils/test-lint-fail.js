// 测试文件：src/utils/test-lint-fail.js
// 失败场景：ESLint 代码质量检查失败（触发 no-undef 规则：使用未声明的变量）
// 说明：undefinedVar 未通过 let/const/var 声明，ESLint 会报 "'undefinedVar' is not defined" 错误

// 故意使用未声明变量，触发ESLint错误
console.log("测试ESLint错误：未声明变量调用");
console.log(undefinedVar); // 核心错误点：undefinedVar 未声明

// 其他正常代码（仅为模拟真实文件结构，不影响错误触发）
export const normalUtils = () => {
  const validVar = "正常变量";
  return validVar;
};
