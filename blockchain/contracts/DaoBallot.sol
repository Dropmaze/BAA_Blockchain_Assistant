// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.20;

/**
 * @title DaoBallot
 * @dev Based on the official Remix "Ballot" contract, extended with
 *      a time-limited voting period.
 */
contract DaoBallot {
    
    struct Voter {
        uint256 weight;      // weight of the vote
        bool voted;          // if true, the voter already voted
        address delegate;    // person delegated to
        uint256 vote;        // index of the voted proposal
    }

    struct Proposal {
        string name;
        uint256 voteCount;
    }

    address public chairperson;
    mapping(address => Voter) public voters;
    Proposal[] public proposals;

    /// @notice Voting is only possible until this timestamp
    uint256 public votingDeadline;

    /**
     * @dev Creates a new ballot with a list of proposal names and sets a voting duration.
     * @param proposalNames Names of proposals
     * @param durationSeconds Voting duration in seconds starting from deployment time
     */
    constructor(string[] memory proposalNames, uint256 durationSeconds) {
        chairperson = msg.sender;
        voters[chairperson].weight = 1;
        votingDeadline = block.timestamp + durationSeconds;

        for (uint256 i = 0; i < proposalNames.length; i++) {
            proposals.push(Proposal({
                name: proposalNames[i],
                voteCount: 0
            }));
        }
    }

    /**
     * @dev Gives the right to vote to a voter. Only callable by the chairperson.
     * @param voter Address of the voter
     */
    function giveRightToVote(address voter) external {
        require(msg.sender == chairperson, "Only chairperson can grant voting rights");
        require(!voters[voter].voted, "The voter already voted");
        require(voters[voter].weight == 0, "Voter already has voting rights");

        voters[voter].weight = 1;
    }

    /**
     * @dev Delegate your vote to another voter.
     * @param to Address to which the vote is delegated
     */
    function delegate(address to) external {
        require(block.timestamp < votingDeadline, "Voting period is over");

        Voter storage sender = voters[msg.sender];
        require(sender.weight != 0, "No right to vote");
        require(!sender.voted, "You already voted");
        require(to != msg.sender, "Self-delegation is not allowed");

        // Follow the delegation chain
        while (voters[to].delegate != address(0)) {
            to = voters[to].delegate;

            // Prevent loops in delegation
            require(to != msg.sender, "Delegation loop detected");
        }

        Voter storage delegate_ = voters[to];
        require(delegate_.weight >= 1, "Delegate has no right to vote");

        sender.voted = true;
        sender.delegate = to;

        if (delegate_.voted) {
            // If delegate already voted, add weight directly to their chosen proposal
            proposals[delegate_.vote].voteCount += sender.weight;
        } else {
            // Otherwise, add weight to the delegate's account
            delegate_.weight += sender.weight;
        }
    }

    /**
     * @dev Cast a vote for a proposal.
     * @param proposal Index of the proposal in the proposals array
     */
    function vote(uint256 proposal) external {
        require(block.timestamp < votingDeadline, "Voting period is over");

        Voter storage sender = voters[msg.sender];
        require(sender.weight != 0, "No right to vote");
        require(!sender.voted, "Already voted");

        sender.voted = true;
        sender.vote = proposal;

        proposals[proposal].voteCount += sender.weight;
    }

    /**
     * @dev Computes the winning proposal based on vote count.
     * @return winningProposal_ Index of the winning proposal
     */
    function winningProposal()
        public
        view
        returns (uint256 winningProposal_)
    {
        uint256 winningVoteCount = 0;

        for (uint256 p = 0; p < proposals.length; p++) {
            if (proposals[p].voteCount > winningVoteCount) {
                winningVoteCount = proposals[p].voteCount;
                winningProposal_ = p;
            }
        }
    }

    /**
     * @dev Returns the name of the winning proposal.
     * @return winnerName_ Name of the winning proposal
     */
    function winnerName()
        external
        view
        returns (string memory winnerName_)
    {
        winnerName_ = proposals[winningProposal()].name;
    }
}