using ContractConfigurator.ExpressionParser;
using System;
using System.Reflection;

namespace RPAxe.Contracts
{
    /// <summary>
    /// Registers the two global CC expression functions a few RP-1 "Commercial Applications"
    /// contracts use. RP-1 returned a player-selected payload count from its RP0 ContractGUI slider
    /// (gone with the plugin); we return a small POSITIVE default. Returning 0 broke those contracts:
    /// they set `minQuantity = @/payload - 0.1`, so payload 0 -> negative minQuantity, which CC
    /// rejects. A positive default keeps them loadable (fixed payload instead of a slider; tune
    /// later). Inherits BaseParser only to reach the protected static RegisterGlobalFunction.
    /// </summary>
    public class AxeExpressionRegistrer : BaseParser, IExpressionParserRegistrer
    {
        // Fixed stand-in payload (RP-1's slider is gone). Must be on the slider's old scale: the
        // comsat contracts compute payload = Round(RP1CommsPayload() * 0.25.., 25) -> a value of 1
        // rounds to 0 -> minQuantity = -0.1 -> CC rejects. 100 -> payload 25 (the contracts' own
        // "baseline of 100" comment). Tune if these commercial contracts matter.
        private const int DEFAULT_PAYLOAD = 100;

        static AxeExpressionRegistrer()
        {
            RegisterGlobalFunction(new Function<int>("RP1CommsPayload", DefaultPayload, false));
            RegisterGlobalFunction(new Function<int>("RP1WeatherPayload", DefaultPayload, false));
        }

        private static int DefaultPayload() => DEFAULT_PAYLOAD;

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
