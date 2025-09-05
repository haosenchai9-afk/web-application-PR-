// 测试文件：src/components/test-build-fail.js
// 失败场景：构建验证失败（导入不存在的依赖包，构建工具无法解析）
// 说明：导入 "non-existent-lib"（虚构依赖），项目未安装该包，构建时会报 "Module not found" 错误

// 核心错误点：导入不存在的依赖包（项目 package.json 中无此依赖）
import NonExistentComponent from "non-existent-lib"; // 虚构依赖，构建时无法找到
import { useState } from "react"; // 正常依赖（对比用，不影响错误触发）

// 模拟React组件（真实项目结构）
const TestBuildFailComponent = () => {
  const [count, setCount] = useState(0);

  return (
    <div className="test-component">
      <h2>测试构建失败组件</h2>
      <p>点击次数：{count}</p>
      <button onClick={() => setCount(count + 1)}>增加计数</button>
      
      {/* 核心错误点：使用不存在的依赖组件，加剧构建失败 */}
      <NonExistentComponent 
        title="虚构组件" 
        content="此组件来自不存在的依赖包" 
      />
    </div>
  );
};

export default TestBuildFailComponent;
