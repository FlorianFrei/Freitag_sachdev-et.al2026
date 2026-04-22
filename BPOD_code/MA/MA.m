
function MA
global BpodSystem 

S = BpodSystem.ProtocolSettings; % settings that can be adjusted during the session
if isempty(fieldnames(S)) 
    S.GUI.ResponseTimeAllowed = 2;
    S.GUI.Flextreshold = 1;
    S.GUI.Flextreshold2 = 0.7;
    S.GUI.Reward_amount= 5;
    S.GUI.reward_delay=1;
end 
BpodParameterGUI('init', S); 
MaxTrials = 1000;

TrialTypes = randsrc(1,MaxTrials,[1 2 3; 0.475 0.475 0.05]);
BpodSystem.Data.TrialTypes = [];

%% Plot
BpodSystem.ProtocolFigures.OutcomePlotFig = figure('Position', [50 540 1000 250],'name','Outcome plot','numbertitle','off', 'MenuBar', 'none', 'Resize', 'off');
BpodSystem.GUIHandles.OutcomePlot = axes('Position', [.075 .3 .89 .6]);
TrialTypeOutcomePlot(BpodSystem.GUIHandles.OutcomePlot,'init',TrialTypes);
BpodNotebook('init'); % Initialize Bpod notebook (for manual data annotation)
BpodParameterGUI('init', S); % Initialize parameter GUI plugin

%% Main trial loop
for currentTrial = 1:MaxTrials
    S = BpodParameterGUI('sync', S); % Sync parameters with BpodParameterGUI plugin
    R = GetValveTimes(S.GUI.Reward_amount, [1 2]);
    LeftValveTime = R(1); RightValveTime = R(2); % Update reward amounts

    switch TrialTypes(currentTrial) % Determine trial-specific state matrix fields
        case 1
            cue = 'Audio'; 
            Reward = 'LeftReward';
        case 2
            cue = 'Airpuff';
            Reward = 'RightReward';
            
        case 3
            cue = 'Audio2Air';
            Reward = 'RightReward';
            
    end
    %% Main loop
    sma = NewStateMachine();

    sma = AddState(sma, 'Name', 'ITI', ... 
        'Timer', normrnd(5,0.75),... 
        'StateChangeConditions', {'Tup', cue},...
        'OutputActions', {'AnalogThreshEnable', 1});

    sma = AddState(sma, 'Name', 'Audio', ...
       'Timer',2,...
        'StateChangeConditions', {'Tup', 'Miss','Flex1Trig1','HIT'},...
        'OutputActions',{'Serial1',49});

    sma = AddState(sma, 'Name', 'Audio2Air', ...
       'Timer',0.5,...
        'StateChangeConditions', {'Tup', 'Airpuff2'},...
        'OutputActions',{'Serial1',49});

    sma = AddState(sma, 'Name', 'Airpuff2', ...
       'Timer',0.25,...
        'StateChangeConditions', {'Tup', 'Hit'},...
        'OutputActions',{'Valve3',1});


    sma = AddState(sma, 'Name', 'Airpuff', ...
       'Timer',0.25,...
        'StateChangeConditions', {'Tup', 'Response_window'},...
        'OutputActions',{'Valve3',1});

    sma = AddState(sma, 'Name', 'Response_window', ...
       'Timer',1,...
        'StateChangeConditions', {'Tup', 'Miss','BNC1High','HIT'},...
        'OutputActions',{'Valve3',1});


    sma = AddState(sma, 'Name', 'Miss','Timer',0.0, ...
        'StateChangeConditions', {'Tup', 'exit'},...
        'OutputActions', {}); 

       sma = AddState(sma, 'Name', 'HIT','Timer',0, ...
        'StateChangeConditions', {'Tup', 'Licking_delay'},...
        'OutputActions', {'BNC1', 1,'Serial1',48}); 

       sma = AddState(sma, 'Name', 'Licking_delay',...
        'Timer',1,...
        'StateChangeConditions', {'Tup', Reward},...
        'OutputActions',{});

       sma = AddState(sma, 'Name', 'LeftReward','Timer',LeftValveTime, ...
        'StateChangeConditions', {'Tup', 'reward_window'},...
        'OutputActions', {'Valve1',1});

       sma = AddState(sma, 'Name', 'RightReward','Timer',RightValveTime, ...
        'StateChangeConditions', {'Tup', 'reward_window'},...
        'OutputActions', {'valve2',1}); 

       sma = AddState(sma, 'Name', 'reward_window','Timer',1, ...
        'StateChangeConditions', {'Tup', 'exit'},...
        'OutputActions', {}); 

    
   %% ?
    SendStateMachine(sma);
    RawEvents = RunStateMachine;
    if ~isempty(fieldnames(RawEvents)) % If trial data was returned
        BpodSystem.Data = AddTrialEvents(BpodSystem.Data,RawEvents); % Computes trial events from raw data
        BpodSystem.Data = BpodNotebook('sync', BpodSystem.Data); % Sync with Bpod notebook plugin
        BpodSystem.Data.TrialSettings(currentTrial) = S; % Adds the settings used for the current trial to the Data struct (to be saved after the trial ends)
        BpodSystem.Data.TrialTypes(currentTrial) = TrialTypes(currentTrial); % Adds the trial type of the current trial to data
        UpdateOutcomePlot(TrialTypes, BpodSystem.Data);
        SaveBpodSessionData; % Saves the field BpodSystem.Data to the current data file
    end
    HandlePauseCondition; % Checks to see if the protocol is paused. If so, waits until user resumes.
    if BpodSystem.Status.BeingUsed == 0
        return
    end
end

function UpdateOutcomePlot(TrialTypes, Data)
global BpodSystem
Outcomes = zeros(1,Data.nTrials);
for x = 1:Data.nTrials
    if ~isnan(Data.RawEvents.Trial{x}.States.Drinking(1))
        Outcomes(x) = 1;
    else
        Outcomes(x) = 3;
    end
end
TrialTypeOutcomePlot(BpodSystem.GUIHandles.OutcomePlot,'update',Data.nTrials+1,TrialTypes,Outcomes);
    


