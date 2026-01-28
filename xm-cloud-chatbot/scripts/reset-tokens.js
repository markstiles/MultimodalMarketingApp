const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

// or sql: DELETE FROM "oAuthToken";

async function main() {
  const deleted = await prisma.oAuthToken.deleteMany({});
  console.log(`Deleted ${deleted.count} OAuth tokens.`);
}

main()
  .catch(e => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
