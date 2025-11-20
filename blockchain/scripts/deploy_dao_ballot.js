import { network } from "hardhat";

const { ethers } = await network.connect({
  network: "localhost", // oder "hardhatMainnet"
});

async function main() {
  const proposals = ["Proposal 1", "Proposal 2", "Proposal 3"];

  const proposalBytes = proposals.map((name) =>
    ethers.encodeBytes32String(name)
  );

  const durationSeconds = 60 * 60 * 24;

  console.log("Deploying DaoBallot contract...");

  const DaoBallot = await ethers.getContractFactory("DaoBallot");
  const daoBallot = await DaoBallot.deploy(proposalBytes, durationSeconds);

  await daoBallot.waitForDeployment();

  const contractAddress = await daoBallot.getAddress();
  const [deployer] = await ethers.getSigners();

  console.log("===========================================");
  console.log(" DaoBallot Deployment Successful!");
  console.log(" Contract Address:", contractAddress);
  console.log(" Chairperson (Deployer):", deployer.address);
  console.log("===========================================");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});