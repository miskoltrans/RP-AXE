By 1950 Kerbalkind is united under one world goverment. They understand that that the universe is blind without us.
--- Ahistorical Xploration & Engineering ---

This is actually my braind dump about axe. 
We will restart the project from start. Maybe it's best to delete almost everything and start over. 

We will build or own tree from scratch.
I think first thing should be to ensure part parity with RP-1 and then we will place the ourselves later.
Actually the parity should be with RO + some things RP1 adds. We would have to research what is the diff between RO clean and RP1 clean isntall, i have both set up. I think RP imposes additional restricitons on parts, which can be good or bad. good use case is reducing part bloat, bad use case is if they cannot find a historical reason for something existing. we are doing ahistorical but grounded in history for education value and plausible designs. that being said i would like to include some part mods, or add new RO configs to make more tech node paths. i suspect rp1 is dense around lunar program, but sparse later.

i am having a conflict in my head about part filosophy, procedural parts will do the most job, they reduce part bloat and give you many options. so no need to include stuff like fuel tanks or adaptors or stuff like that and that is aligned with rp1 philosophy. historical parts do have some education value in giving you blueprints and even flavour. in the tech tree i would like for technologies to have flavour text, note. i am thinking about including probes like raider nicks us and soviet probes, and i see that there is a conflict between tree and probes because probes are integrated composite parts, and tech tree advances technologies, so it very hard to place a probe which uses multiple tecnologis like micorporocessors or very advanced solar or something. and then i though i can make probes both optional and work. so my idea is if you have us probes or soviet probes mods you get two nodes like hire JPL people, or hire OKB people which open up a subtree for probes, and we will make probe blueprint unlockable there, but the acutal parts will have a checklist of technilogies which you need to have before you place them in vab or fly them like:"
[✓] High-Density Silicon Logic (Electronics Branch - Tier 2)
[✗] Vacuum Induction Melting (Metallurgy Branch - Tier 3)
[✓] Hydrazine Handling Protocol (Chemistry Branch - Tier 1)"

now after probes i notice that we home some other parts which are integrated parts like capsules from RO capsules, not sure how integrated they are and what do we do with them in the end. It is great that you unlock lunar module stuff in one part of the tree, actual engine in another, legs in third, etc. so you even get aha moments when you make them fit, or you go for your own designs, you have freedom. maybe capsules are not that integrated, and tree even though it's free because of nature of science will have some gates, so it might work out in the end. 

for capsules we might take an aporoach where you unlock the capsule in one node but added capabilites in other nodes. like life support when you unlock you can set it uo and use in your capsules. note why would you have a part if its not usable, but maybr even stripped down capsules have some utility

So i wanna start with RO part list + RP1 added parts. then see what rp1 blacklists from RO. We will be doing blacklisting or addding new configs to support the vision long term. Some additional mods i wanna explore and include:
Dmagic orbital science - probably hard dependency and we will balance sicence with this in mind. since it's not maintained but works on latest ksp version might have to bundle in
SCansat - gives you more reasons to send probes, but we will have to fork it and create work hard to fix ram consumption. still want it as hard dependency
raider nick probes - recomended but optional
tantares - if they make meaningfull aditions - many parts don't have ro config, and they should not have like tanks and shiet. ro engines might be good enoguh for engines.
coatl airpsace redux - ro has configs for some parts like antenas and shit, we might do it we might not if it plays well with the tree
nerteas mods - kerbal atomics, near future solar/constructin/electrica/propulsion/spacecraft - maybe ro is to restritive and we willl look for inspiration here to add parts for later stages
far future technologies - same as above but lower priority.
universal storage 2 - didnt try it but it being modular might mesh well with procedural parts to give more possibilities.
sspx - for station builders
stockish project orion - looks recomended by ro, complete alt history, which makes it a good fit - does not exist on ckan we will have to bundle it with our mod.
Kerwis Chinese Aerospace Pack  - maybe for china flavor

to check might be redundant or not needed:
cryo Engines

rocket motor managerie
near future launch vehicles
near future exploration


visual:
firefly - recomend
z theme - recomend
hullcam - recomend
vab organizer - recommend
milky way - recomend

we will need a "simulation" mod, rp1 includes something that seems highly integrated with RP1 mechanics like reliability data gathering which we will sack, but i think id recomend to players to have a testing mod to test shit it various orbits or plantes before launching a mission makes the design process easier. maybe even gamify it, unlock simulation after researching computers.

i would create a submod later that deletes unused parts from game directory to save ram and loading time. maybe this even exists.

Now that  i menioned this, how do you know what the state of default RP-1 install: there is ../ksp_rp_clean, that will stay there clean.
After we ensure parity with clean rp1 we will be adding new mods later. axe replaces rp1 so all depencies of axe will be mods installed in ../ksp_rp_clean at the start, we will have to figure out a way to update dependencies for axe later. We will do it this way to make it eaiser to rebuild a testing instance by copying ../ksp_instance_clean and installing axe + dependencies to it.
Anyways.
We will steal contracts from RP-1. I think we did a good job on it in current axe so leave that in.
Central piece of the mod is the tech tree which we will redesign from scrach. Note: i cloned ETT, we can use some things from that tree, like tech tree editor.
I like that you choose start x-planes or rockets and i like that tree is engineering focused and not by eras.

I will drop a concept of the tree from a chat, don't take it as gospell we should try to improve on this initial design
--
🚀 The Core Philosophy
Instead of using generic sci-fi names or arbitrary timelines, this tech tree is governed entirely by thermodynamics, material limits, and real industrial processes. It treats the player like a systems architect rather than someone filling a progress bar.

🛠️ The 3 Structural Pillars
1. Functional Branches, Real Names
Every node represents an actual historical or modern industrial breakthrough. You don’t unlock generic "Advanced Engines"; you unlock Full-Flow Staged Combustion (FFSC) or Vacuum Induction Melting (VIM).

2. Scattered Themes (Anti-Exploit Design)
Instead of dedicated "Science" or "Mining" branches that can be easily rushed, utility parts are scattered organically based on the engineering required to build and operate them:

Mystery Goo and Materials Studies are moved to the Metallurgy line (because they are heavy, structural sample boxes that face massive atmospheric and thermal stress).

3. Convergence Gates & Multi-Entry Paths
The tree completely breaks away from flat, linear progressions to simulate real-world system integration:

Convergence Gates (anyToUnlock = False): Advanced parts require multiple disciplines to meet. You cannot build a reusable Methalox drive without mastering high-pressure metallurgy and automated computer fluid timing simultaneously.

Multi-Entry Paths (anyToUnlock = True): Multiple design philosophies can solve the same goal. You can choose to navigate deep space using a complex Optical Star-Tracking network or a massive Ground-Based Radio Antenna network.

🎯 The Mechanical Impact
With unlimited funding, the game economy entirely shifts. You are never bottlenecked by cash or calendar build times; you are bottlenecked by Power Grids, Heat Dissipation, and Material Limits. To launch a heavy, advanced payload, you are forced to run a balanced space program where structures, electrical lines, and life support systems mature in absolute harmony.
--
^ money economy will exist because it adds to some engineering challenges, it is used to abstract non simulated engineering tradeoffs.
tree will have some branches, some will split graft etc. but we will not do like a line of rocketry until the endgame. 

Number of nodes should be min 200, max 500. I think we need 200 to make all rp1 parts (including upgrades) have their home. But we will be adding ahistorical nodes later like atomics, near future far future etc.
It is not expected to finish the whole tree in a playthrough. Maybe total tree cost == total science in the universe is a good starting point. We will balance the game around DMagic orbital science mod additions, so like more experiments. We will need a way to rebalance the tree and edit it after initial version.

Tree should be balanced on multiple axes. Science is the primary and most important resource. Parts will have initial purchasing cost simulating additional rnd costs. launch costs are simulating additional operational complexities like hydrazine handling.

we will sack rp1 feature of gathering run data to improve reliability its tedious and only slows down the progression. our game should be filled with what if scenarios and focus on enigneering challenges. grounded in historical and plausible parts and technologies. i have slight conflict here in my head. most of the gemplay will be driven by procedural part, but i want to include both historical and stockish things because histocircal partse or crafts give you blueprints to lrarn from and add educational value. i would add education as 4th pillar afer ahistorical, exploration, engineering.

We did good job with avionics, we will fix bugs there later but design is sound. we should rename it to match rp1. we will have to revisit avionics balance for sure. 

how should we do mod support, should we let mods add ther parts into our tree or we curate everythin? 

contracts re fine for now but we might be changing that system as well. what is someone wants to focus on von brown mars project. But in general i think it's a good idea to grade node costs by tiers since there is a natural progression in ksp after orbit. I would want to understand all numbers for balancig this tree. 

we need to figure out better workflows for things. like i need a way to test adding new mods for parts, but also we need a way to test the clean + recomended installation. the default starting point is rp1 express installation minus rp1 for dependencies. 

I will need you help me make all of this this actionable.

I have many more things in my head that i have worked out but i forgot to write them down.

you should be able to change the location of KSC to wherever you like, whenever you like. this is part of the game. 


Note science: kerbalism lab experiments expanded
