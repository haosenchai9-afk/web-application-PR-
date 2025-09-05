// 测试文件：tests/utils/test-fail.test.js
// 失败场景：Jest 测试执行失败（断言结果不匹配）
// 说明：sum(1,1) 实际结果为 2，但断言为 3，触发测试失败

// 导入待测试的工具函数（模拟真实项目结构）
import { sum } from "../../src/utils/normal-utils"; // 假设项目有正常工具函数文件

// 测试用例1：正常场景（仅为对比，不影响失败结果）
test("sum(2,3) 应返回 5（正常用例）", () => {
  expect(sum(2, 3)).toBe(5); // 此用例正常通过
});

// 测试用例2：失败场景（核心错误用例）
test("sum(1,1) 故意断言为 3（触发测试失败）", () => {
  const result = sum(1, 1); // 实际结果：2
  expect(result).toBe(3); // 核心错误点：断言结果与实际结果不匹配，Jest 报 "Expected: 3, Received: 2"
});

// 工具函数模拟（若项目无 normal-utils.js，可直接在此定义，避免导入错误）
// export const sum = (a, b) => a + b;
