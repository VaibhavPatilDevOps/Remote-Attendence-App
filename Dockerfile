# Base Node.js image
FROM docker.io/library/node:20.15.0 AS base

# Set working directory
WORKDIR /usr/app

# Copy package.json and tsconfig.json
COPY package.json tsconfig.json ./

# Install pnpm globally
RUN npm install -g pnpm@8.x

# Install all dependencies, including dev dependencies
RUN pnpm install

# Install a specific version of TypeScript
RUN pnpm add typescript@5.5.4 --save-dev

# Copy the rest of the application code
COPY . .

# Stage 1: Development environment
FROM base AS development

# Install nodemon globally
RUN npm install -g nodemon

# Expose application port
EXPOSE 5000

# Command to run your application in development
CMD ["pnpm", "run", "start:dev"]

# Stage 2: Production environment
FROM base AS production

# Install only production dependencies
RUN pnpm install --production

# Install a specific version of TypeScript
RUN pnpm add typescript@5.5.4 --save-dev

# Build the application (this assumes tsc is available)
RUN pnpm run build

# Expose application port
EXPOSE 5000

# Command to run your application in production
CMD ["pnpm", "start"]
