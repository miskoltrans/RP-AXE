using ContractConfigurator.ExpressionParser;
using System;
using System.Reflection;

namespace RPAxe.Contracts
{
    /// <summary>
    /// Registers the two global CC expression functions a few RP-1 "Commercial Applications"
    /// contracts use in their reward formulas. RP-1 returned a live payload count from its RP0
    /// ContractGUI; we stub them to 0 so those contracts parse (their payload-scaled reward terms
    /// just contribute nothing). Inherits BaseParser only to reach the protected static
    /// RegisterGlobalFunction (same pattern as RP-1's CustomExpressionParserRegistrer).
    /// </summary>
    public class AxeExpressionRegistrer : BaseParser, IExpressionParserRegistrer
    {
        static AxeExpressionRegistrer()
        {
            RegisterGlobalFunction(new Function<int>("RP1CommsPayload", Zero, false));
            RegisterGlobalFunction(new Function<int>("RP1WeatherPayload", Zero, false));
        }

        private static int Zero() => 0;

        public void RegisterExpressionParsers() { }

        public override MethodInfo methodParseStatementInner => throw new NotImplementedException();
        public override MethodInfo methodGetRval => throw new NotImplementedException();
        public override MethodInfo methodApplyBooleanOperator => throw new NotImplementedException();
        public override MethodInfo methodParseStatement => throw new NotImplementedException();
        public override MethodInfo methodParseMethod => throw new NotImplementedException();
        public override MethodInfo methodCompleteIdentifierParsing => throw new NotImplementedException();
        public override MethodInfo method_ConvertType => throw new NotImplementedException();

        public override void ExecuteAndStoreExpression(string key, string expression, DataNode dataNode) => throw new NotImplementedException();
        public override object ParseExpressionGeneric(string key, string expression, DataNode dataNode) => throw new NotImplementedException();
    }
}
