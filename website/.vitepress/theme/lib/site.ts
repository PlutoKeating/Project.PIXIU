const repository = import.meta.env.VITE_GITHUB_REPOSITORY || 'PlutoKeating/Project.PIXIU';
if (!/^[\w.-]+\/[\w.-]+$/.test(repository)) throw new Error('Invalid public GitHub repository');
export const site = {
  repository,
  github: `https://github.com/${repository}`,
  api: `https://api.github.com/repos/${repository}`,
};
