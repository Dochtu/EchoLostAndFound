using System;
using System.Collections.Generic;
using System.Diagnostics;
using EchoLostAndFound.Shared.Contracts;

namespace EchoLostAndFound.Tests
{
    internal static class Assert
    {
        public static void True(bool condition, string message = null)
        {
            if (!condition) throw new AssertionException(message ?? "条件应为 true。");
        }

        public static void False(bool condition, string message = null)
        {
            if (condition) throw new AssertionException(message ?? "条件应为 false。");
        }

        public static void Null(object value, string message = null)
        {
            if (value != null) throw new AssertionException(message ?? "期望为 null，实际为 " + value + "。");
        }

        public static void NotNull(object value, string message = null)
        {
            if (value == null) throw new AssertionException(message ?? "期望非 null。");
        }

        public static void Equal<T>(T expected, T actual, string message = null)
        {
            if (!EqualityComparer<T>.Default.Equals(expected, actual))
                throw new AssertionException((message ?? "值不相等。") + " 期望=" + expected + "，实际=" + actual + "。");
        }

        public static void NotEqual<T>(T unexpected, T actual, string message = null)
        {
            if (EqualityComparer<T>.Default.Equals(unexpected, actual))
                throw new AssertionException((message ?? "值不应相等。") + " 值=" + actual + "。");
        }

        public static void SequenceEqual(IReadOnlyList<string> expected, IReadOnlyList<string> actual, string message = null)
        {
            if (expected.Count != actual.Count)
                throw new AssertionException(
                    (message ?? "序列长度不同。") + " 期望=[" + string.Join(",", expected) + "]，实际=[" + string.Join(",", actual) + "]。");
            for (var i = 0; i < expected.Count; i++)
            {
                if (!string.Equals(expected[i], actual[i], StringComparison.Ordinal))
                    throw new AssertionException(
                        (message ?? "序列元素不同。") + " 索引 " + i + " 期望=" + expected[i] + "，实际=" + actual[i] + "。");
            }
        }

        public static void Contains(string expectedSubstring, string actual, string message = null)
        {
            if (actual == null || actual.IndexOf(expectedSubstring, StringComparison.Ordinal) < 0)
                throw new AssertionException((message ?? "子串缺失。") + " 期望包含=" + expectedSubstring + "，实际=" + actual + "。");
        }

        /// <summary>Asserts that the action throws a GameContractException with the given error code.</summary>
        public static void ContractCode(Action action, string expectedCode, string message = null)
        {
            try
            {
                action();
            }
            catch (GameContractException ex)
            {
                Equal(expectedCode, ex.Code, message);
                return;
            }

            throw new AssertionException((message ?? "期望抛出契约错误。") + " 期望错误码=" + expectedCode + "。");
        }

        /// <summary>Asserts that the action throws a contract error and returns it for further checks.</summary>
        public static GameContractException ThrowsContract(Action action, string message = null)
        {
            try
            {
                action();
            }
            catch (GameContractException ex)
            {
                return ex;
            }

            throw new AssertionException(message ?? "期望抛出 GameContractException。");
        }

        public static void Throws<TException>(Action action, string message = null) where TException : Exception
        {
            try
            {
                action();
            }
            catch (TException)
            {
                return;
            }
            catch (Exception ex)
            {
                throw new AssertionException((message ?? "抛出的异常类型不符。") + " 期望=" + typeof(TException).Name + "，实际=" + ex.GetType().Name + "。");
            }

            throw new AssertionException((message ?? "期望抛出异常。") + " 期望=" + typeof(TException).Name + "。");
        }
    }

    internal sealed class AssertionException : Exception
    {
        public AssertionException(string message) : base(message)
        {
        }
    }

    internal sealed class TestCase
    {
        public TestCase(string name, Action body)
        {
            Name = name;
            Body = body;
        }

        public string Name { get; }

        public Action Body { get; }
    }

    internal sealed class TestRegistry
    {
        private readonly List<TestCase> tests = new List<TestCase>();

        public void Add(string name, Action body)
        {
            tests.Add(new TestCase(name, body));
        }

        public int RunAll()
        {
            var passed = 0;
            var failed = 0;
            var stopwatch = new Stopwatch();
            Console.WriteLine("== EchoLostAndFound M3-B tests ==");
            foreach (var test in tests)
            {
                stopwatch.Restart();
                try
                {
                    test.Body();
                    stopwatch.Stop();
                    passed++;
                    Console.WriteLine("PASS  " + test.Name + "  (" + stopwatch.ElapsedMilliseconds + " ms)");
                }
                catch (Exception ex)
                {
                    stopwatch.Stop();
                    failed++;
                    Console.WriteLine("FAIL  " + test.Name + "  (" + stopwatch.ElapsedMilliseconds + " ms)");
                    Console.WriteLine("      " + ex.GetType().Name + ": " + ex.Message);
                    if (!(ex is AssertionException))
                    {
                        Console.WriteLine(ex.StackTrace);
                    }
                }
            }

            Console.WriteLine();
            Console.WriteLine("Total: " + tests.Count + "  Passed: " + passed + "  Failed: " + failed);
            return failed == 0 ? 0 : 1;
        }
    }
}
