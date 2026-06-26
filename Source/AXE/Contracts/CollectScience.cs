using Contracts;
using ContractConfigurator;
using System.Collections.Generic;
using System.Linq;

namespace RPAxe.Contracts
{
    // `PARAMETER { type = RP1CollectScience }` — simplified per project direction ("transmit
    // science could be enough"): completes when science is received (recovered OR transmitted) for
    // a matching subject. Matching = an explicit `subject` id, or any `experiment` id (optionally
    // on `targetBody`). RP-1's fractional / per-biome aggregation is intentionally dropped.
    public class RP1CollectScienceFactory : ParameterFactory
    {
        protected List<ScienceExperiment> experiment;
        protected List<ScienceSubject> subjects;

        public override bool Load(ConfigNode configNode)
        {
            bool valid = base.Load(configNode);
            // Fold the parse results into `valid` so a renamed/missing experiment or subject id fails
            // the factory loudly at load, instead of silently degrading to "any science, anywhere"
            // (the empty-filter match=true fallthrough below).
            valid &= ConfigNodeUtil.ParseValue(configNode, "experiment", x => experiment = x, this, new List<ScienceExperiment>());
            valid &= ConfigNodeUtil.ParseValue(configNode, "subject", x => subjects = x, this, new List<ScienceSubject>());
            return valid;
        }

        public override ContractParameter Generate(Contract contract)
        {
            List<string> expIds = experiment != null ? experiment.Where(e => e != null).Select(e => e.id).ToList() : new List<string>();
            List<string> subjIds = subjects != null ? subjects.Where(s => s != null).Select(s => s.id).ToList() : new List<string>();
            return new RP1CollectScience(title, expIds, subjIds, targetBody);
        }
    }

    public class RP1CollectScience : ContractParameter
    {
        private string _title;
        private List<string> expIds = new List<string>();
        private List<string> subjIds = new List<string>();
        private string bodyName;
        private bool done;

        public RP1CollectScience() { }

        public RP1CollectScience(string title, List<string> expIds, List<string> subjIds, CelestialBody body)
        {
            _title = title;
            this.expIds = expIds ?? new List<string>();
            this.subjIds = subjIds ?? new List<string>();
            bodyName = body != null ? body.name : null;
        }

        protected override string GetTitle() => string.IsNullOrEmpty(_title) ? "Collect and return science" : _title;

        protected override void OnRegister() { GameEvents.OnScienceRecieved.Add(OnScienceReceived); }
        protected override void OnUnregister() { GameEvents.OnScienceRecieved.Remove(OnScienceReceived); }

        private void OnScienceReceived(float amount, ScienceSubject subject, ProtoVessel pv, bool reverse)
        {
            if (done || subject == null || amount <= 0f) return;
            string id = subject.id;
            bool match;
            if (subjIds.Count > 0)
                match = subjIds.Contains(id);
            else if (expIds.Count > 0)
                match = expIds.Any(e => id.StartsWith(e));
            else
                match = true;

            if (match && (string.IsNullOrEmpty(bodyName) || id.Contains(bodyName)))
            {
                done = true;
                SetComplete();
            }
        }

        protected override void OnSave(ConfigNode node)
        {
            node.AddValue("done", done);
            node.AddValue("title", _title ?? "");
            if (!string.IsNullOrEmpty(bodyName)) node.AddValue("bodyName", bodyName);
            foreach (string e in expIds) node.AddValue("expId", e);
            foreach (string s in subjIds) node.AddValue("subjId", s);
        }

        protected override void OnLoad(ConfigNode node)
        {
            bool.TryParse(node.GetValue("done"), out done);
            _title = node.GetValue("title");
            bodyName = node.GetValue("bodyName");
            expIds = node.GetValues("expId").ToList();
            subjIds = node.GetValues("subjId").ToList();
            if (done) SetComplete();
        }
    }
}
