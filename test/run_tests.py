"""
运行所有测试
"""
import unittest

def run_tests():
    """运行所有测试"""
    # 发现并运行所有测试
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover('test', pattern='test_*.py')
    
    # 运行测试
    test_runner = unittest.TextTestRunner(verbosity=2)
    test_runner.run(test_suite)

if __name__ == '__main__':
    run_tests() 