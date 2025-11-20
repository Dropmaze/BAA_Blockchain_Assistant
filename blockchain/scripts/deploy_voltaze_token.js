import { network } from "hardhat";

const { ethers } = await network.connect({
  network: "localhost",
});

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deployer:", deployer.address);

  const VoltazeToken = await ethers.getContractFactory("VoltazeToken");

  const initialSupply = ethers.parseUnits("1000000", 18);

  console.log("Deploying VoltazeToken...");
  const token = await VoltazeToken.deploy(initialSupply);
  await token.waitForDeployment();

  console.log("VoltazeToken deployed to:", await token.getAddress());
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});