import { network } from "hardhat";

const { ethers } = await network.connect({
  network: "localhost",
});

async function main() {
  const proposals = [
    "Soll ein neues offizielles Logo eingeführt werden?",
    "Soll ein jährliches gemeinsames Team-Event organisiert werden?"
  ];

  const durationSeconds = 60 * 60 * 24;

  console.log("Deploying DaoBallot contract...");

  const DaoBallot = await ethers.getContractFactory("DaoBallot");
  const daoBallot = await DaoBallot.deploy(proposals, durationSeconds);

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
  process.exit(1);
});